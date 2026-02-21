from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class FeedbackUpsertRequest(BaseModel):
    review_label: Literal["malicious", "benign"]
    review_note: str | None = Field(default=None, max_length=4000)


class FeedbackResponse(BaseModel):
    analysis_id: str
    review_label: str
    review_note: str | None = None
    reviewed_by: str
    reviewed_at: datetime


class FeedbackEventResponse(BaseModel):
    id: str
    analysis_id: str
    old_review_label: str | None = None
    new_review_label: str | None = None
    old_review_note: str | None = None
    new_review_note: str | None = None
    changed_by: str
    changed_at: datetime
