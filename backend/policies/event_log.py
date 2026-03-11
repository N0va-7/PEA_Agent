from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.models.tables import PolicyEvent


POLICY_KEYS = (
    "sender_whitelist",
    "sender_blacklist",
    "domain_blacklist",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_values(values: Iterable[str] | None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in values or []:
        value = str(item or "").strip().lower()
        if not value or value in seen:
            continue
        seen.add(value)
        cleaned.append(value)
    return cleaned


def _make_event(
    *,
    event_type: str,
    policy_key: str,
    policy_value: str,
    action: str,
    actor: str | None = None,
    analysis_id: str | None = None,
    details: dict | None = None,
) -> PolicyEvent:
    return PolicyEvent(
        id=str(uuid4()),
        event_type=event_type,
        policy_key=policy_key,
        policy_value=policy_value,
        action=action,
        actor=actor,
        analysis_id=analysis_id,
        details=details or None,
        created_at=_now(),
    )


def record_policy_update_events(
    db: Session,
    *,
    policy_key: str,
    previous_values: Iterable[str] | None,
    next_values: Iterable[str] | None,
    actor: str | None,
):
    before = set(_normalize_values(previous_values))
    after = set(_normalize_values(next_values))
    for value in sorted(after - before):
        db.add(
            _make_event(
                event_type="policy_update",
                policy_key=policy_key,
                policy_value=value,
                action="added",
                actor=actor,
            )
        )
    for value in sorted(before - after):
        db.add(
            _make_event(
                event_type="policy_update",
                policy_key=policy_key,
                policy_value=value,
                action="removed",
                actor=actor,
            )
        )


def record_policy_hit_events(
    db: Session,
    *,
    analysis_id: str,
    policy_evaluation: dict | None,
):
    payload = policy_evaluation or {}
    mapping = {
        "sender_whitelist": payload.get("sender_whitelist"),
        "sender_blacklist": payload.get("sender_blacklist"),
        "domain_blacklist": payload.get("domain_blacklist"),
    }
    for policy_key, raw_value in mapping.items():
        value = str(raw_value or "").strip().lower()
        if not value:
            continue
        db.add(
            _make_event(
                event_type="policy_hit",
                policy_key=policy_key,
                policy_value=value,
                action="hit",
                analysis_id=analysis_id,
            )
        )


def list_recent_policy_events(db: Session, *, limit: int = 50) -> list[PolicyEvent]:
    stmt = select(PolicyEvent).order_by(desc(PolicyEvent.created_at)).limit(limit)
    return list(db.execute(stmt).scalars().all())


def build_policy_summary(
    db: Session,
    *,
    current_policies: dict[str, list[str]],
) -> dict[str, list[dict]]:
    hit_rows = db.execute(
        select(
            PolicyEvent.policy_key,
            PolicyEvent.policy_value,
            func.count().label("hit_count"),
            func.max(PolicyEvent.created_at).label("last_hit_at"),
        )
        .where(PolicyEvent.event_type == "policy_hit")
        .group_by(PolicyEvent.policy_key, PolicyEvent.policy_value)
    ).all()
    hit_map = {
        (str(row.policy_key), str(row.policy_value)): {
            "hit_count": int(row.hit_count or 0),
            "last_hit_at": row.last_hit_at.isoformat() if row.last_hit_at else None,
        }
        for row in hit_rows
    }

    summary: dict[str, list[dict]] = {}
    for policy_key in POLICY_KEYS:
        items: list[dict] = []
        for value in _normalize_values(current_policies.get(policy_key, [])):
            latest_update = db.execute(
                select(PolicyEvent)
                .where(
                    PolicyEvent.event_type == "policy_update",
                    PolicyEvent.policy_key == policy_key,
                    PolicyEvent.policy_value == value,
                )
                .order_by(desc(PolicyEvent.created_at))
                .limit(1)
            ).scalar_one_or_none()
            hit_info = hit_map.get((policy_key, value), {})
            items.append(
                {
                    "value": value,
                    "hit_count": int(hit_info.get("hit_count") or 0),
                    "last_hit_at": hit_info.get("last_hit_at"),
                    "last_changed_at": latest_update.created_at.isoformat() if latest_update else None,
                    "last_changed_by": latest_update.actor if latest_update else None,
                    "last_change_action": latest_update.action if latest_update else None,
                }
            )
        summary[policy_key] = items
    return summary
