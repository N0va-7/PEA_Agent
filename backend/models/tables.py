from datetime import datetime, timezone

from sqlalchemy import JSON as SAJSON
from sqlalchemy import DateTime, Index, Integer, String, Text
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

    parsed_email: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    url_extraction: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    url_reputation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    url_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    content_review: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    attachment_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    decision: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    report_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_path: Mapped[str] = mapped_column(Text, nullable=False)
    execution_trace: Mapped[list | None] = mapped_column(JSON, nullable=True)
    review_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


Index("idx_email_analyses_message_id", EmailAnalysis.message_id)
Index("idx_email_analyses_created_at", EmailAnalysis.created_at)
Index("idx_email_analyses_review_label", EmailAnalysis.review_label)
Index("idx_email_analyses_reviewed_at", EmailAnalysis.reviewed_at)


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


class AnalysisFeedbackEvent(Base):
    __tablename__ = "analysis_feedback_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    analysis_id: Mapped[str] = mapped_column(String(64), nullable=False)
    old_review_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    new_review_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    old_review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


Index("idx_feedback_events_analysis_id", AnalysisFeedbackEvent.analysis_id)
Index("idx_feedback_events_changed_at", AnalysisFeedbackEvent.changed_at)


class SystemConfig(Base):
    __tablename__ = "system_config"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class PolicyEvent(Base):
    __tablename__ = "policy_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    policy_key: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_value: Mapped[str] = mapped_column(String(512), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    actor: Mapped[str | None] = mapped_column(String(128), nullable=True)
    analysis_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


Index("idx_policy_events_type", PolicyEvent.event_type)
Index("idx_policy_events_key_value", PolicyEvent.policy_key, PolicyEvent.policy_value)
Index("idx_policy_events_created_at", PolicyEvent.created_at)


class VTUrlCache(Base):
    __tablename__ = "vt_url_cache"

    url_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    normalized_url: Mapped[str] = mapped_column(Text, nullable=False)
    vt_url_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    http_status: Mapped[int] = mapped_column(nullable=False, default=200)


Index("idx_vt_url_cache_expires_at", VTUrlCache.expires_at)


class UrlAnalysis(Base):
    __tablename__ = "url_analyses"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    requested_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_url: Mapped[str] = mapped_column(Text, nullable=False)
    url_reputation: Mapped[dict | None] = mapped_column(SAJSON, nullable=True)
    url_analysis: Mapped[dict | None] = mapped_column(SAJSON, nullable=True)
    decision: Mapped[dict | None] = mapped_column(SAJSON, nullable=True)
    execution_trace: Mapped[list | None] = mapped_column(SAJSON, nullable=True)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


Index("idx_url_analyses_updated_at", UrlAnalysis.updated_at)
