from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.db import Base, session_scope
from app.db_models import AnalysisCacheModel, AnalysisJobModel, QuarantineRecordModel, SampleObjectModel
from app.models import AnalysisResult, CachedAnalysis, JobRecord, JobStatus, QuarantineRecord, Verdict


class Repository:
    def __init__(self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.engine = engine
        self.session_factory = session_factory

    async def initialize(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def upsert_sample(
        self,
        *,
        sha256: str,
        object_ref: str,
        filename: str,
        declared_mime: str | None,
        size_bytes: int,
    ) -> None:
        async with session_scope(self.session_factory) as session:
            existing = await session.get(SampleObjectModel, sha256)
            if existing is None:
                session.add(
                    SampleObjectModel(
                        sha256=sha256,
                        object_ref=object_ref,
                        filename=filename,
                        declared_mime=declared_mime,
                        size_bytes=size_bytes,
                    )
                )
                return
            existing.object_ref = object_ref
            existing.filename = filename
            existing.declared_mime = declared_mime
            existing.size_bytes = size_bytes

    async def get_sample_by_ref(self, object_ref: str) -> SampleObjectModel | None:
        async with session_scope(self.session_factory) as session:
            result = await session.execute(select(SampleObjectModel).where(SampleObjectModel.object_ref == object_ref))
            return result.scalar_one_or_none()

    async def create_job(self, job: JobRecord) -> JobRecord:
        async with session_scope(self.session_factory) as session:
            session.add(
                AnalysisJobModel(
                    job_id=job.job_id,
                    sample_sha256=job.sample_sha256,
                    filename=job.filename,
                    declared_mime=job.declared_mime,
                    source_id=job.source_id,
                    object_ref=job.object_ref,
                    status=job.status.value,
                    created_at=job.created_at,
                    updated_at=job.updated_at,
                )
            )
        return job

    async def get_job(self, job_id: str) -> JobRecord | None:
        async with session_scope(self.session_factory) as session:
            row = await session.get(AnalysisJobModel, job_id)
            if row is None:
                return None
            return row_to_job(row)

    async def list_jobs(self, limit: int = 50) -> list[JobRecord]:
        async with session_scope(self.session_factory) as session:
            result = await session.execute(
                select(AnalysisJobModel).order_by(AnalysisJobModel.updated_at.desc()).limit(max(1, min(limit, 200)))
            )
            rows = result.scalars().all()
            return [row_to_job(row) for row in rows]

    async def mark_job_running(self, job_id: str) -> JobRecord | None:
        async with session_scope(self.session_factory) as session:
            row = await session.get(AnalysisJobModel, job_id)
            if row is None:
                return None
            if row.status != JobStatus.QUEUED.value:
                return None
            row.status = JobStatus.RUNNING.value
            row.updated_at = utcnow()
            await session.flush()
            return row_to_job(row)

    async def complete_job(self, job_id: str, result: AnalysisResult, sample_sha256: str, source_id: str) -> JobRecord | None:
        async with session_scope(self.session_factory) as session:
            row = await session.get(AnalysisJobModel, job_id)
            if row is None:
                return None
            row.status = JobStatus.COMPLETED.value
            row.verdict = result.verdict.value
            row.risk_score = result.risk_score
            row.reasons = result.reasons
            row.normalized_type = result.normalized_type
            row.artifacts = result.artifacts
            row.rule_version = result.rule_version
            row.error_message = None
            row.updated_at = utcnow()
            row.audit_log = {
                "sample_sha256": sample_sha256,
                "source_id": source_id,
                "reasons": result.reasons,
                "rule_version": result.rule_version,
                "verdict": result.verdict.value,
            }
            await session.flush()
            return row_to_job(row)

    async def fail_job(self, job_id: str, error_message: str, rule_version: str) -> JobRecord | None:
        async with session_scope(self.session_factory) as session:
            row = await session.get(AnalysisJobModel, job_id)
            if row is None:
                return None
            row.status = JobStatus.COMPLETED.value
            row.verdict = Verdict.ERROR.value
            row.risk_score = 100
            row.reasons = ["PARSER_FAILURE"]
            row.normalized_type = "unknown"
            row.artifacts = []
            row.rule_version = rule_version
            row.error_message = error_message
            row.updated_at = utcnow()
            row.audit_log = {
                "sample_sha256": row.sample_sha256,
                "source_id": row.source_id,
                "reasons": row.reasons,
                "rule_version": rule_version,
                "verdict": row.verdict,
                "error": error_message,
            }
            await session.flush()
            return row_to_job(row)

    async def get_cached_analysis(self, sample_sha256: str, rule_version: str) -> CachedAnalysis | None:
        async with session_scope(self.session_factory) as session:
            result = await session.execute(
                select(AnalysisCacheModel).where(
                    AnalysisCacheModel.sample_sha256 == sample_sha256,
                    AnalysisCacheModel.rule_version == rule_version,
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return CachedAnalysis(
                sample_sha256=row.sample_sha256,
                rule_version=row.rule_version,
                verdict=Verdict(row.verdict),
                risk_score=row.risk_score,
                reasons=list(row.reasons or []),
                normalized_type=row.normalized_type,
                artifacts=list(row.artifacts or []),
            )

    async def upsert_cached_analysis(self, sample_sha256: str, result: AnalysisResult) -> None:
        async with session_scope(self.session_factory) as session:
            db_result = await session.execute(
                select(AnalysisCacheModel).where(
                    AnalysisCacheModel.sample_sha256 == sample_sha256,
                    AnalysisCacheModel.rule_version == result.rule_version,
                )
            )
            row = db_result.scalar_one_or_none()
            if row is None:
                session.add(
                    AnalysisCacheModel(
                        sample_sha256=sample_sha256,
                        rule_version=result.rule_version,
                        verdict=result.verdict.value,
                        risk_score=result.risk_score,
                        reasons=result.reasons,
                        normalized_type=result.normalized_type,
                        artifacts=result.artifacts,
                    )
                )
                return
            row.verdict = result.verdict.value
            row.risk_score = result.risk_score
            row.reasons = result.reasons
            row.normalized_type = result.normalized_type
            row.artifacts = result.artifacts
            row.updated_at = utcnow()

    async def put_quarantine_record(self, record: QuarantineRecord) -> None:
        async with session_scope(self.session_factory) as session:
            existing = await session.execute(
                select(QuarantineRecordModel).where(QuarantineRecordModel.job_id == record.job_id)
            )
            row = existing.scalar_one_or_none()
            if row is None:
                session.add(
                    QuarantineRecordModel(
                        job_id=record.job_id,
                        sample_sha256=record.sample_sha256,
                        reasons=record.reasons,
                        created_at=record.created_at,
                    )
                )
                return
            row.reasons = record.reasons

    async def list_quarantine(self) -> list[dict]:
        async with session_scope(self.session_factory) as session:
            result = await session.execute(select(QuarantineRecordModel).order_by(QuarantineRecordModel.id))
            rows = result.scalars().all()
            return [
                {
                    "job_id": row.job_id,
                    "sample_sha256": row.sample_sha256,
                    "reasons": list(row.reasons or []),
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ]

    async def recover_incomplete_jobs(self, older_than_seconds: int) -> list[str]:
        cutoff = utcnow() - timedelta(seconds=older_than_seconds)
        async with session_scope(self.session_factory) as session:
            queued_result = await session.execute(
                select(AnalysisJobModel).where(AnalysisJobModel.status == JobStatus.QUEUED.value)
            )
            running_result = await session.execute(
                select(AnalysisJobModel).where(
                    AnalysisJobModel.status == JobStatus.RUNNING.value,
                    AnalysisJobModel.updated_at < cutoff,
                )
            )
            queued_rows = queued_result.scalars().all()
            stale_running_rows = running_result.scalars().all()
            for row in stale_running_rows:
                row.status = JobStatus.QUEUED.value
                row.updated_at = utcnow()
            job_ids = [row.job_id for row in queued_rows] + [row.job_id for row in stale_running_rows]
            return list(dict.fromkeys(job_ids))


def row_to_job(row: AnalysisJobModel) -> JobRecord:
    return JobRecord(
        job_id=row.job_id,
        sample_sha256=row.sample_sha256,
        filename=row.filename,
        declared_mime=row.declared_mime,
        source_id=row.source_id,
        object_ref=row.object_ref,
        status=JobStatus(row.status),
        verdict=Verdict(row.verdict) if row.verdict else None,
        risk_score=row.risk_score,
        reasons=list(row.reasons or []),
        normalized_type=row.normalized_type,
        artifacts=list(row.artifacts or []),
        rule_version=row.rule_version,
        created_at=ensure_aware(row.created_at),
        updated_at=ensure_aware(row.updated_at),
        error_message=row.error_message,
        audit_log=dict(row.audit_log or {}),
    )


def ensure_aware(value: datetime | None) -> datetime:
    if value is None:
        return utcnow()
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def utcnow() -> datetime:
    return datetime.now(tz=UTC)
