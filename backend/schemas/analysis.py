from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AnalysisResponse(BaseModel):
    id: str
    message_id: str | None = None
    fingerprint: str
    sender: str | None = None
    recipient: str | None = None
    subject: str | None = None
    url_analysis: dict[str, Any] | None = None
    body_analysis: dict[str, Any] | None = None
    attachment_analysis: dict[str, Any] | None = None
    final_decision: dict[str, Any] | None = None
    llm_report: str | None = None
    report_path: str
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
