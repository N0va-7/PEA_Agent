from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EmailPayload(BaseModel):
    message_id: str | None = None
    sender: str | None = None
    recipient: str | None = None
    subject: str | None = None
    urls: list[str] = Field(default_factory=list)
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class ToolOutputsPayload(BaseModel):
    url_extraction: dict[str, Any] | None = None
    url_reputation: dict[str, Any] | None = None
    url_analysis: dict[str, Any] | None = None
    content_review: dict[str, Any] | None = None
    attachment_analysis: dict[str, Any] | None = None


class ReportPayload(BaseModel):
    markdown: str | None = None
    path: str


class AnalysisResponse(BaseModel):
    id: str
    fingerprint: str
    email: EmailPayload
    tool_outputs: ToolOutputsPayload
    decision: dict[str, Any] | None = None
    report: ReportPayload
    execution_trace: list[Any] | None = None
    review_label: str | None = None
    review_note: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime


class AnalysisListResponse(BaseModel):
    items: list[AnalysisResponse]
    total: int
    page: int
    page_size: int
    sort_by: str
    sort_order: str
    limit: int
    offset: int


class AnalysisDeleteResponse(BaseModel):
    deleted_count: int
