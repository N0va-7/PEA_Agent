from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

JSONType = SQLITE_JSON


class SampleObjectModel(Base):
    __tablename__ = "sample_objects"

    sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    object_ref: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(512))
    declared_mime: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    stored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AnalysisJobModel(Base):
    __tablename__ = "analysis_jobs"

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sample_sha256: Mapped[str] = mapped_column(String(64), index=True)
    filename: Mapped[str] = mapped_column(String(512))
    declared_mime: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_id: Mapped[str] = mapped_column(String(255), index=True)
    object_ref: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), index=True)
    verdict: Mapped[str | None] = mapped_column(String(32), nullable=True)
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reasons: Mapped[list] = mapped_column(JSONType, default=list)
    normalized_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    artifacts: Mapped[list] = mapped_column(JSONType, default=list)
    rule_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    audit_log: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class AnalysisCacheModel(Base):
    __tablename__ = "analysis_cache"
    __table_args__ = (UniqueConstraint("sample_sha256", "rule_version", name="uq_cache_sha_rule"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sample_sha256: Mapped[str] = mapped_column(String(64), index=True)
    rule_version: Mapped[str] = mapped_column(String(128))
    verdict: Mapped[str] = mapped_column(String(32))
    risk_score: Mapped[int] = mapped_column(Integer)
    reasons: Mapped[list] = mapped_column(JSONType, default=list)
    normalized_type: Mapped[str] = mapped_column(String(64))
    artifacts: Mapped[list] = mapped_column(JSONType, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class QuarantineRecordModel(Base):
    __tablename__ = "quarantine_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    sample_sha256: Mapped[str] = mapped_column(String(64), index=True)
    reasons: Mapped[list] = mapped_column(JSONType, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
