from pydantic import BaseModel


class DomainListResponse(BaseModel):
    domains: list[str]
    updated_at: str | None = None


class DomainListUpdateRequest(BaseModel):
    domains: list[str]


class PolicySummaryItem(BaseModel):
    value: str
    hit_count: int = 0
    last_hit_at: str | None = None
    last_changed_at: str | None = None
    last_changed_by: str | None = None
    last_change_action: str | None = None


class PolicySummaryResponse(BaseModel):
    sender_whitelist: list[PolicySummaryItem]
    sender_blacklist: list[PolicySummaryItem]
    domain_blacklist: list[PolicySummaryItem]


class PolicyEventResponse(BaseModel):
    id: str
    event_type: str
    policy_key: str
    policy_value: str
    action: str
    actor: str | None = None
    analysis_id: str | None = None
    created_at: str


class PolicyEventListResponse(BaseModel):
    items: list[PolicyEventResponse]
