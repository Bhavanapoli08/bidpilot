"""
Jobs API: poll the status of background processing tasks.
"""
from fastapi import APIRouter, Depends
from app.auth.dependencies import get_current_org
from app.models import Organization
from app.schemas import JobStatusResponse
from app.jobs.celery_config import celery_app

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    _: Organization = Depends(get_current_org),
):
    """Poll a Celery job's status and progress."""
    task = celery_app.AsyncResult(job_id)

    response = JobStatusResponse(job_id=job_id, status=task.status)

    if task.status == "PROGRESS" and isinstance(task.info, dict):
        current = task.info.get("current", 0)
        total = task.info.get("total", 1)
        response.progress = round((current / total) * 100, 1) if total else 0
    elif task.status == "SUCCESS":
        response.result = task.result if isinstance(task.result, dict) else None
    elif task.status == "FAILURE":
        response.error = str(task.info)

    return response
