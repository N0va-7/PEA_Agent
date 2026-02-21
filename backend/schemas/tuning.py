from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FusionPrecheckRequest(BaseModel):
    reviewed_from: datetime | None = None
    reviewed_to: datetime | None = None
    fpr_target: float = Field(default=0.03, ge=0.0001, le=0.5)
    w_step: float = Field(default=0.05, gt=0, le=1)
    th_min: float = Field(default=0.50, ge=0.0, le=1.0)
    th_max: float = Field(default=0.95, ge=0.0, le=1.0)
    th_step: float = Field(default=0.01, gt=0, le=1)


class FusionPrecheckResponse(BaseModel):
    meets_requirements: bool
    blocking_reasons: list[str] = Field(default_factory=list)
    valid_rows: int
    skipped_rows: int
    positive_rows: int
    negative_rows: int
    recent_feedback_rows: int
    min_total_required: int
    min_class_required: int
    recent_days_required: int


class FusionRunRequest(FusionPrecheckRequest):
    confirm: bool = False


class FusionRunResponse(BaseModel):
    run_id: str
    status: str
    triggered_at: datetime
    precheck: FusionPrecheckResponse
    result_json_path: str | None = None
    best_params: dict[str, Any] | None = None


class FusionRunItem(BaseModel):
    id: str
    status: str
    triggered_by: str
    triggered_at: datetime
    finished_at: datetime | None = None
    activated_at: datetime | None = None
    is_active: bool
    row_count: int
    positive_count: int
    negative_count: int
    skipped_count: int
    recent_feedback_count: int
    result_json_path: str | None = None
    best_params: dict[str, Any] | None = None
    selection_reason: str | None = None
    error: str | None = None


class FusionRunListResponse(BaseModel):
    items: list[FusionRunItem]


class FusionActivateResponse(BaseModel):
    run_id: str
    active_run_id: str
    activated_at: datetime
