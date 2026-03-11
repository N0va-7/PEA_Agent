from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class URLCheckRequest(BaseModel):
    urls: list[str] = Field(default_factory=list)


class URLToolOutputsPayload(BaseModel):
    url_reputation: dict[str, Any] | None = None
    url_analysis: dict[str, Any] | None = None


class URLCheckResponse(BaseModel):
    id: str
    requested_url: str
    normalized_url: str
    tool_outputs: URLToolOutputsPayload
    decision: dict[str, Any] | None = None
    execution_trace: list[Any] | None = None
    request_count: int = 1
    is_cached_result: bool = False
    created_at: datetime
    updated_at: datetime


class URLCheckBatchResponse(BaseModel):
    items: list[URLCheckResponse]
    submitted_count: int
    reused_count: int
    created_count: int


class URLCheckListResponse(BaseModel):
    items: list[URLCheckResponse]
    total: int
    page: int
    page_size: int
