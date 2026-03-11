from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.models import JobStatus, Verdict


class JsonJobCreateRequest(BaseModel):
    filename: str
    source_id: str
    declared_mime: str | None = None
    content_sha256: str | None = None
    object_ref: str | None = None
    content_base64: str | None = None

    @model_validator(mode="after")
    def validate_source(self) -> "JsonJobCreateRequest":
        if not self.object_ref and not self.content_base64:
            raise ValueError("either object_ref or content_base64 is required")
        return self


class JobCreateResponse(BaseModel):
    job_id: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    verdict: Verdict | None = None
    risk_score: int | None = Field(default=None, ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)
    normalized_type: str | None = None
    artifacts: list[dict] = Field(default_factory=list)
    rule_version: str | None = None
    sample_sha256: str
    source_id: str
    filename: str | None = None
    declared_mime: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    error_message: str | None = None


class JobListResponse(BaseModel):
    items: list[JobStatusResponse] = Field(default_factory=list)


class RuleSummaryResponse(BaseModel):
    path: str
    editable: bool
    source_kind: str
    rule_names: list[str] = Field(default_factory=list)
    size_bytes: int = Field(ge=0)


class RuleListResponse(BaseModel):
    rules_version: str
    rules: list[RuleSummaryResponse] = Field(default_factory=list)


class RuleDetailResponse(RuleSummaryResponse):
    content: str


class RuleWriteRequest(BaseModel):
    path: str
    content: str


class RuleMutationResponse(BaseModel):
    rule: RuleDetailResponse
    rules_version: str
