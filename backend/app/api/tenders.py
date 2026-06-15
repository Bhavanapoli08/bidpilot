"""
Tenders API: upload, list, retrieve, analysis, Q&A, delete.
"""
import os
import tempfile
import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.auth.dependencies import get_current_org, get_current_user
from app.models import Tender, TenderAnalysis, TenderStatus, Organization, User
from app.schemas import (
    TenderUploadResponse,
    TenderResponse,
    TenderStatusResponse,
    TenderAnalysisResponse,
    TenderQARequest,
    TenderQAResponse,
)
from app.storage.s3_service import s3_service
from app.billing.usage_tracker import usage_tracker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tenders", tags=["tenders"])

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


@router.post("/upload", response_model=TenderUploadResponse)
async def upload_tender(
    file: UploadFile = File(...),
    org: Organization = Depends(get_current_org),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a tender PDF -> store in S3 -> enqueue processing job."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Enforce monthly quota
    usage_tracker.check_quota(db, str(org.id))

    # Persist to temp file
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 50MB limit")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    # Create DB record first to get an ID
    tender = Tender(
        organization_id=org.id,
        file_name=file.filename,
        s3_key="",  # filled after upload
        file_size=len(contents),
        status=TenderStatus.PENDING,
    )
    db.add(tender)
    db.commit()
    db.refresh(tender)

    try:
        upload_result = await s3_service.upload_tender_pdf(
            str(org.id), str(tender.id), tmp_path, len(contents)
        )
        tender.s3_key = upload_result["s3_key"]
        tender.file_hash = upload_result["file_hash"]
        db.commit()
    finally:
        os.unlink(tmp_path)

    # Enqueue background processing. If the broker (Redis) is unreachable, the
    # file is still safely stored — we just can't queue analysis, so report that
    # instead of 500-ing the whole upload.
    usage_tracker.increment(db, str(org.id))
    job_id = ""
    status = "queued"
    message = "Tender uploaded and queued for processing"
    if _broker_reachable():
        from app.jobs.tasks import process_tender_pdf
        task = process_tender_pdf.apply_async(
            args=[str(tender.id), str(org.id)],
            queue="high_priority",
        )
        tender.job_id = job_id = task.id
        db.commit()
    else:
        logger.warning("Broker unreachable; tender %s stored but not queued", tender.id)
        status = "stored"
        message = (
            "Tender stored, but background processing is unavailable "
            "(Redis/Celery not running). Start the worker stack to analyze it."
        )

    return TenderUploadResponse(
        tender_id=tender.id,
        job_id=job_id,
        status=status,
        message=message,
    )


def _broker_reachable(timeout: float = 3.0) -> bool:
    """Quick liveness check of the Celery broker so a missing Redis doesn't hang uploads.

    A plain TCP connect is enough: it cleanly distinguishes "nothing listening"
    (fast connection-refused) from "broker is up". We deliberately do NOT perform a
    TLS handshake here — for a remote broker like Upstash (rediss://) the handshake
    adds ~500ms and previously blew a tight timeout, falsely reporting the broker as
    down and silently skipping job enqueue.
    """
    import socket
    from urllib.parse import urlparse

    parsed = urlparse(settings.CELERY_BROKER_URL)
    host, port = parsed.hostname or "localhost", parsed.port or 6379
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@router.get("", response_model=list[TenderResponse])
async def list_tenders(
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """List all tenders for the current organization."""
    tenders = (
        db.query(Tender)
        .filter(Tender.organization_id == org.id)
        .order_by(Tender.created_at.desc())
        .all()
    )
    return tenders


@router.get("/{tender_id}", response_model=TenderResponse)
async def get_tender(
    tender_id: UUID,
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Get a single tender by ID (org-scoped)."""
    tender = (
        db.query(Tender)
        .filter(Tender.id == tender_id, Tender.organization_id == org.id)
        .first()
    )
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    return TenderStatusResponse(
        tender_id=tender.id,
        status=tender.status,
        page_count=tender.page_count,
        processed_at=tender.processed_at,
        error_message=tender.error_message,
    )


@router.get("/{tender_id}/status", response_model=TenderStatusResponse)
async def get_tender_status(
    tender_id: UUID,
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Check processing status of a tender."""
    tender = (
        db.query(Tender)
        .filter(Tender.id == tender_id, Tender.organization_id == org.id)
        .first()
    )
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    return tender


@router.get("/{tender_id}/analysis", response_model=TenderAnalysisResponse)
async def get_tender_analysis(
    tender_id: UUID,
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Get extracted analysis for a tender."""
    analysis = (
        db.query(TenderAnalysis)
        .filter(
            TenderAnalysis.tender_id == tender_id,
            TenderAnalysis.organization_id == org.id,
        )
        .first()
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not ready or not found")
    return analysis


@router.post("/{tender_id}/ask", response_model=TenderQAResponse)
async def ask_tender(
    tender_id: UUID,
    request: TenderQARequest,
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Ask a question about a tender; answer is grounded with citations."""
    tender = (
        db.query(Tender)
        .filter(Tender.id == tender_id, Tender.organization_id == org.id)
        .first()
    )
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    if tender.status != TenderStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="Tender still processing")

    from app.rag.citation_handler import citation_handler
    result = citation_handler.answer_with_citations(
        str(tender_id), request.question, str(org.id), request.top_k
    )

    return TenderQAResponse(
        answer=result["answer"],
        sources=result["citations"],
        confidence=result["confidence"],
    )


@router.get("/{tender_id}/download")
async def download_tender(
    tender_id: UUID,
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Get a signed URL to download the original PDF."""
    tender = (
        db.query(Tender)
        .filter(Tender.id == tender_id, Tender.organization_id == org.id)
        .first()
    )
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    # Local mode: stream the file directly. S3 mode: hand back a signed URL.
    if getattr(s3_service, "local_mode", False):
        path = s3_service._local_file(str(org.id), str(tender_id))
        if not path.exists():
            raise HTTPException(status_code=404, detail="Stored file not found")
        return FileResponse(path, media_type="application/pdf", filename=tender.file_name)

    url = s3_service.generate_signed_url(str(org.id), str(tender_id))
    return {"download_url": url, "expires_in": 3600}


@router.delete("/{tender_id}")
async def delete_tender(
    tender_id: UUID,
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Delete a tender and its vectors."""
    tender = (
        db.query(Tender)
        .filter(Tender.id == tender_id, Tender.organization_id == org.id)
        .first()
    )
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    from app.rag.vector_store import vector_store
    vector_store.delete_tender(str(org.id), str(tender_id))

    db.delete(tender)
    db.commit()
    return {"status": "deleted", "tender_id": str(tender_id)}
