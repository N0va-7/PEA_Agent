from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.tables import AnalysisJob


class JobRepository:
    def create(
        self,
        db: Session,
        job_id: str,
        *,
        current_stage: str | None = None,
        progress_events: list[dict] | None = None,
    ) -> AnalysisJob:
        now = datetime.now(timezone.utc)
        job = AnalysisJob(
            id=job_id,
            status="queued",
            current_stage=current_stage,
            progress_events=progress_events or [],
            created_at=now,
            updated_at=now,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    def get_by_id(self, db: Session, job_id: str) -> Optional[AnalysisJob]:
        return db.get(AnalysisJob, job_id)

    def mark_running(self, db: Session, job_id: str):
        job = db.get(AnalysisJob, job_id)
        if not job:
            return
        job.status = "running"
        job.current_stage = "running"
        job.updated_at = datetime.now(timezone.utc)
        db.commit()

    def append_progress_event(self, db: Session, job_id: str, event: dict, *, current_stage: str | None = None):
        job = db.get(AnalysisJob, job_id)
        if not job:
            return
        existing = list(job.progress_events or [])
        payload = dict(event)
        payload.setdefault("seq", len(existing) + 1)
        existing.append(payload)
        job.progress_events = existing
        if current_stage is not None:
            job.current_stage = current_stage
        job.updated_at = datetime.now(timezone.utc)
        db.commit()

    def mark_finished(self, db: Session, job_id: str, *, status: str, analysis_id: str | None, error: str | None = None):
        job = db.get(AnalysisJob, job_id)
        if not job:
            return
        job.status = status
        job.current_stage = status
        job.analysis_id = analysis_id
        job.error = error
        job.updated_at = datetime.now(timezone.utc)
        db.commit()
