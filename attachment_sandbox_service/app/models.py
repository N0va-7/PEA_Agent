from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


class Verdict(str, Enum):
    ALLOW = "allow"
    QUARANTINE = "quarantine"
    BLOCK = "block"
    ERROR = "error"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class AttachmentObject:
    sha256: str
    content: bytes
    filename: str
    declared_mime: str | None
    stored_at: datetime = field(default_factory=utcnow)


@dataclass(frozen=True, slots=True)
class FeatureHit:
    reason: str
    score: int
    evidence: str
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    verdict: Verdict
    risk_score: int
    reasons: list[str]
    normalized_type: str
    artifacts: list[dict[str, Any]]
    feature_hits: list[FeatureHit]
    rule_version: str


@dataclass(frozen=True, slots=True)
class CachedAnalysis:
    sample_sha256: str
    rule_version: str
    verdict: Verdict
    risk_score: int
    reasons: list[str]
    normalized_type: str
    artifacts: list[dict[str, Any]]


@dataclass(slots=True)
class JobRecord:
    sample_sha256: str
    filename: str
    declared_mime: str | None
    source_id: str
    object_ref: str
    job_id: str = field(default_factory=lambda: str(uuid4()))
    status: JobStatus = JobStatus.QUEUED
    verdict: Verdict | None = None
    risk_score: int | None = None
    reasons: list[str] = field(default_factory=list)
    normalized_type: str | None = None
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    rule_version: str | None = None
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)
    error_message: str | None = None
    audit_log: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class QuarantineRecord:
    job_id: str
    sample_sha256: str
    reasons: list[str]
    created_at: datetime = field(default_factory=utcnow)
