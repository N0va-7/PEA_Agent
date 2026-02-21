from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.infra.db import Base


class EmailAnalysis(Base):
    __tablename__ = "email_analyses"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    message_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)

    sender: Mapped[str | None] = mapped_column(String(512), nullable=True)
    recipient: Mapped[str | None] = mapped_column(String(512), nullable=True)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)

    url_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    body_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    attachment_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    final_decision: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    llm_report: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_path: Mapped[str] = mapped_column(Text, nullable=False)
    execution_trace: Mapped[list | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


Index("idx_email_analyses_message_id", EmailAnalysis.message_id)
Index("idx_email_analyses_created_at", EmailAnalysis.created_at)


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    current_stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    analysis_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress_events: Mapped[list | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


Index("idx_analysis_jobs_status", AnalysisJob.status)
