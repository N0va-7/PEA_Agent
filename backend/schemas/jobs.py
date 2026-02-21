from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class JobCreateResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    id: str
    status: str
    analysis_id: str | None = None
    error: str | None = None
    current_stage: str | None = None
    current_stage_label: str | None = None
    completed_stages: list[str] = Field(default_factory=list)
    completed_stage_labels: list[str] = Field(default_factory=list)
    progress_events: list[dict[str, Any]] = Field(default_factory=list)
    total_stages: int | None = None
    created_at: datetime
    updated_at: datetime
