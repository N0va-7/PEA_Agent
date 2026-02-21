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


class FusionTuningRun(Base):
    __tablename__ = "fusion_tuning_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    triggered_by: Mapped[str] = mapped_column(String(128), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=False, nullable=False)

    reviewed_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fpr_target: Mapped[float] = mapped_column(nullable=False, default=0.03)
    w_step: Mapped[float] = mapped_column(nullable=False, default=0.05)
    th_min: Mapped[float] = mapped_column(nullable=False, default=0.50)
    th_max: Mapped[float] = mapped_column(nullable=False, default=0.95)
    th_step: Mapped[float] = mapped_column(nullable=False, default=0.01)

    row_count: Mapped[int] = mapped_column(nullable=False, default=0)
    positive_count: Mapped[int] = mapped_column(nullable=False, default=0)
    negative_count: Mapped[int] = mapped_column(nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(nullable=False, default=0)
    recent_feedback_count: Mapped[int] = mapped_column(nullable=False, default=0)
    precheck: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    dataset_csv_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    best_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    top_k: Mapped[list | None] = mapped_column(JSON, nullable=True)
    selection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


Index("idx_fusion_tuning_runs_status", FusionTuningRun.status)
Index("idx_fusion_tuning_runs_triggered_at", FusionTuningRun.triggered_at)
Index("idx_fusion_tuning_runs_is_active", FusionTuningRun.is_active)


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
