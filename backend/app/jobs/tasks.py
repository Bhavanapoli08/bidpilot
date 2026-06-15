"""
Celery background tasks: PDF processing pipeline.

process_tender_pdf:
  S3 download -> text extract (+OCR fallback) -> chunk -> embed
  -> Qdrant upsert -> field extraction -> persist analysis.
"""
import io
import logging
from datetime import datetime
from app.jobs.celery_config import celery_app
from app.config import settings
from app.database import SessionLocal
from app.models import Tender, TenderAnalysis, TenderStatus

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, queue="default")
def process_tender_pdf(self, tender_id: str, org_id: str):
    """Full processing pipeline for an uploaded tender PDF."""
    db = SessionLocal()
    tender = None
    try:
        import pdfplumber
        from app.storage.s3_service import s3_service
        from app.rag.embedder import embedder, chunk_text
        from app.rag.vector_store import vector_store

        tender = db.query(Tender).filter(Tender.id == tender_id).first()
        if not tender:
            logger.error(f"Tender {tender_id} not found")
            return {"status": "error", "reason": "tender_not_found"}

        tender.status = TenderStatus.PROCESSING
        tender.job_id = self.request.id
        db.commit()

        # 1. Download PDF bytes from S3
        pdf_bytes = _download_sync(s3_service, org_id, tender_id)

        # 2. Extract text page by page (with OCR fallback)
        full_text = ""
        page_map = []
        scanned = False

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            total = len(pdf.pages)
            for i, page in enumerate(pdf.pages):
                self.update_state(state="PROGRESS", meta={"current": i + 1, "total": total})
                text = page.extract_text() or ""

                # OCR fallback for image-only pages
                if len(text.strip()) < 20:
                    text = _ocr_page(page)
                    scanned = True

                full_text += text + "\n"
                page_map.append({"page_num": i + 1, "text": text})

        # 3. Chunk
        chunks = chunk_text(full_text, chunk_size=2000, overlap=200, page_map=page_map)
        for c in chunks:
            c["org_id"] = org_id
            c["tender_id"] = tender_id

        # 4. Embed + 5. Upsert to Qdrant
        embedded = embedder.embed_chunks(chunks)
        vector_store.upsert_chunks(embedded)

        # 6. Extract structured fields
        from app.rag.extractor import tender_extractor
        extracted = tender_extractor.extract_all(tender_id, org_id)
        summary = tender_extractor.generate_summary(tender_id, org_id, extracted)

        # 7. Persist analysis
        _persist_analysis(db, tender_id, org_id, extracted, summary)

        # 8. Mark complete
        tender.status = TenderStatus.COMPLETED
        tender.page_count = len(page_map)
        tender.is_scanned = scanned
        tender.processed_at = datetime.utcnow()
        db.commit()

        logger.info(f"Tender {tender_id} processed: {len(chunks)} chunks, {len(page_map)} pages")
        return {"status": "success", "chunks": len(chunks), "pages": len(page_map)}

    except Exception as exc:
        logger.exception(f"Processing failed for tender {tender_id}")
        if tender:
            tender.status = TenderStatus.FAILED
            tender.error_message = str(exc)[:500]
            db.commit()
        countdown = 5 * (5 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)
    finally:
        db.close()


def _download_sync(s3_service, org_id: str, tender_id: str) -> bytes:
    """Synchronous download (Celery workers aren't async). Works for S3 or local."""
    return s3_service.download_bytes(org_id, tender_id)


def _ocr_page(page) -> str:
    """OCR a single page using Tesseract."""
    try:
        import pytesseract
        image = page.to_image(resolution=200)
        return pytesseract.image_to_string(image.original)
    except Exception as e:
        logger.warning(f"OCR failed: {e}")
        return ""


def _persist_analysis(db, tender_id, org_id, extracted, summary):
    """Write extracted fields into TenderAnalysis."""
    def val(field):
        return extracted.get(field, {}).get("value")

    deadline = None
    raw_deadline = val("bid_deadline")
    if raw_deadline:
        try:
            deadline = datetime.fromisoformat(str(raw_deadline).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    tender_value = None
    raw_value = val("tender_value")
    if isinstance(raw_value, (int, float)):
        tender_value = raw_value

    sector = val("sector")
    if isinstance(sector, list):
        sector = sector[0] if sector else None

    analysis = db.query(TenderAnalysis).filter(
        TenderAnalysis.tender_id == tender_id
    ).first()

    if analysis:
        analysis.summary = summary
        analysis.tender_value = tender_value
        analysis.bid_deadline = deadline
        analysis.sector = sector
        analysis.location = val("location")
        analysis.eligibility_criteria = val("financial_criteria") or []
        analysis.required_documents = val("required_documents") or []
        analysis.penalty_clauses = val("penalty_clauses") or []
    else:
        analysis = TenderAnalysis(
            tender_id=tender_id,
            organization_id=org_id,
            summary=summary,
            tender_value=tender_value,
            bid_deadline=deadline,
            sector=sector,
            location=val("location"),
            eligibility_criteria=val("financial_criteria") or [],
            required_documents=val("required_documents") or [],
            penalty_clauses=val("penalty_clauses") or [],
        )
        db.add(analysis)
    db.commit()


@celery_app.task(queue="default")
def get_job_status(job_id: str):
    """Return Celery task status (used by status endpoint)."""
    result = celery_app.AsyncResult(job_id)
    return {"job_id": job_id, "status": result.status}


# ==================== SCHEDULED: MONITORING ====================
@celery_app.task(queue="low_priority")
def scan_tender_sources(org_id: str = None):
    """Poll active tender sources for new opportunities.

    Run for one org (org_id given) or sweep every org with active sources
    (beat-scheduled, org_id=None). Each new opportunity is matched against the
    company profile; high matches raise alerts.
    """
    from app.monitoring.scanner import scan_organization
    from app.models import TenderSource

    db = SessionLocal()
    try:
        if org_id:
            org_ids = [org_id]
        else:
            org_ids = [
                str(oid) for (oid,) in db.query(TenderSource.organization_id)
                .filter(TenderSource.is_active.is_(True))
                .distinct()
                .all()
            ]

        totals = {"orgs": 0, "new": 0, "alerts": 0}
        for oid in org_ids:
            result = scan_organization(db, oid)
            totals["orgs"] += 1
            totals["new"] += result["new"]
            totals["alerts"] += result["alerts"]

        logger.info("scan_tender_sources: %s", totals)
        return totals
    except Exception:
        logger.exception("scan_tender_sources failed")
        raise
    finally:
        db.close()


# ==================== SCHEDULED: DEADLINE ALERTS ====================
@celery_app.task(queue="low_priority")
def scan_deadlines(org_id: str = None):
    """Fire deadline alerts for active bids approaching submission dates."""
    from app.notifications.deadline_sweep import sweep_deadlines

    db = SessionLocal()
    try:
        result = sweep_deadlines(db, organization_id=org_id)
        logger.info("scan_deadlines: %s", result)
        return result
    except Exception:
        logger.exception("scan_deadlines failed")
        raise
    finally:
        db.close()
