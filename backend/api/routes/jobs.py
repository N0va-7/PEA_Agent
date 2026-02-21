from fastapi import APIRouter, Depends, status

from backend.api.deps import get_container, require_auth
from backend.container import AppContainer
from backend.infra.errors import raise_api_error
from backend.schemas.jobs import JobStatusResponse


router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[Depends(require_auth)])


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str, container: AppContainer = Depends(get_container)):
    job = container.analysis_service.get_job(job_id)
    if not job:
        raise_api_error(status_code=status.HTTP_404_NOT_FOUND, code="job_not_found", message="Job not found")
    progress = container.analysis_service.get_job_progress(job_id) or {}
    return JobStatusResponse(
        id=job.id,
        status=job.status,
        analysis_id=job.analysis_id,
        error=job.error,
        current_stage=progress.get("current_stage") or job.current_stage,
        current_stage_label=progress.get("current_stage_label"),
        completed_stages=progress.get("completed_stages", []),
        completed_stage_labels=progress.get("completed_stage_labels", []),
        progress_events=progress.get("progress_events", list(job.progress_events or [])),
        total_stages=progress.get("total_stages"),
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
