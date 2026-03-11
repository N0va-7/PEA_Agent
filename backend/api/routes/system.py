import json
from urllib.parse import parse_qs, urlparse

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete
from sqlalchemy.engine.url import make_url

from backend.api.deps import get_container, get_current_user, require_auth
from backend.container import AppContainer
from backend.models.tables import SystemConfig
from backend.policies.event_log import build_policy_summary, list_recent_policy_events, record_policy_update_events
from backend.schemas.system import (
    DomainListResponse,
    DomainListUpdateRequest,
    PolicyEventListResponse,
    PolicyEventResponse,
    PolicySummaryResponse,
)


router = APIRouter(prefix="/system", tags=["system"], dependencies=[Depends(require_auth)])
SENDER_WHITELIST_KEY = "sender_whitelist"
SENDER_BLACKLIST_KEY = "sender_blacklist"
DOMAIN_BLACKLIST_KEY = "domain_blacklist"


def _safe_db_info(database_url: str) -> dict:
    try:
        url = make_url(database_url)
    except Exception:
        return {"driver": "unknown", "display": "invalid_database_url"}

    driver = (url.drivername or "unknown").strip()
    if driver.startswith("sqlite"):
        db_name = str(url.database or "")
        return {
            "driver": driver,
            "host": "local-file",
            "port": None,
            "database": db_name,
            "username": None,
            "has_password": False,
            "display": f"{driver}://local-file/{db_name}",
        }

    return {
        "driver": driver,
        "host": url.host,
        "port": url.port,
        "database": url.database,
        "username": url.username,
        "has_password": bool(url.password),
        "display": f"{driver}://{url.host}:{url.port}/{url.database}",
    }


def _safe_redis_info(redis_url: str, backend: str) -> dict:
    if backend != "redis":
        return {"backend": backend, "enabled": False}

    parsed = urlparse(redis_url or "")
    qs = parse_qs(parsed.query)
    db = 0
    if parsed.path and parsed.path != "/":
        try:
            db = int(parsed.path.lstrip("/"))
        except ValueError:
            db = 0
    elif "db" in qs and qs["db"]:
        try:
            db = int(qs["db"][0])
        except ValueError:
            db = 0

    return {
        "backend": backend,
        "enabled": True,
        "host": parsed.hostname,
        "port": parsed.port,
        "db": db,
        "username": parsed.username,
        "has_password": bool(parsed.password),
        "display": f"redis://{parsed.hostname}:{parsed.port}/{db}",
    }


def _normalize_domain(value: str) -> str:
    text = str(value or "").strip().lower().rstrip(".")
    if not text:
        return ""
    if "@" in text:
        text = text.split("@", 1)[1].strip()
    return text


def _normalize_sender(value: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if "<" in text and ">" in text:
        start = text.rfind("<")
        end = text.rfind(">")
        if start >= 0 and end > start:
            text = text[start + 1 : end].strip()
    return text if "@" in text else ""


def _normalize_domain_list(values: list[str] | None) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in values:
        domain = _normalize_domain(item)
        if not domain or domain in seen:
            continue
        seen.add(domain)
        normalized.append(domain)
    return normalized


def _normalize_sender_list(values: list[str] | None) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in values:
        sender = _normalize_sender(item)
        if not sender or sender in seen:
            continue
        seen.add(sender)
        normalized.append(sender)
    return normalized


def _load_domain_list(container: AppContainer, key: str) -> tuple[list[str], str | None]:
    with container.analysis_service.session_factory() as db:
        row = db.get(SystemConfig, key)
        if not row or not row.value:
            return [], None
        try:
            payload = json.loads(row.value)
        except json.JSONDecodeError:
            return [], row.updated_at.isoformat() if row.updated_at else None
        return _normalize_domain_list(payload if isinstance(payload, list) else []), (
            row.updated_at.isoformat() if row.updated_at else None
        )


def _load_sender_list(container: AppContainer, key: str) -> tuple[list[str], str | None]:
    with container.analysis_service.session_factory() as db:
        row = db.get(SystemConfig, key)
        if not row or not row.value:
            return [], None
        try:
            payload = json.loads(row.value)
        except json.JSONDecodeError:
            return [], row.updated_at.isoformat() if row.updated_at else None
        return _normalize_sender_list(payload if isinstance(payload, list) else []), (
            row.updated_at.isoformat() if row.updated_at else None
        )


def _get_current_values(container: AppContainer, key: str, *, sender_mode: bool) -> list[str]:
    loader = _load_sender_list if sender_mode else _load_domain_list
    values, _ = loader(container, key)
    return values


@router.get("/runtime-info")
def get_runtime_info(container: AppContainer = Depends(get_container)):
    settings = container.settings
    return {
        "database": _safe_db_info(settings.database_url),
        "queue": _safe_redis_info(settings.redis_url, settings.job_queue_backend),
        "model_dir": str(settings.model_dir),
        "upload_dir": str(settings.upload_dir),
        "report_output_dir": str(settings.report_output_dir),
    }


@router.get("/sender-whitelist", response_model=DomainListResponse)
def get_sender_whitelist(container: AppContainer = Depends(get_container)):
    values, updated_at = _load_sender_list(container, SENDER_WHITELIST_KEY)
    return DomainListResponse(domains=values, updated_at=updated_at)


@router.put("/sender-whitelist", response_model=DomainListResponse)
def update_sender_whitelist(
    payload: DomainListUpdateRequest,
    container: AppContainer = Depends(get_container),
    current_user: str = Depends(get_current_user),
):
    values = _normalize_sender_list(payload.domains)
    previous_values = _get_current_values(container, SENDER_WHITELIST_KEY, sender_mode=True)
    with container.analysis_service.session_factory() as db:
        if values:
            row = db.get(SystemConfig, SENDER_WHITELIST_KEY)
            if row is None:
                row = SystemConfig(key=SENDER_WHITELIST_KEY, value=json.dumps(values, ensure_ascii=False))
                db.add(row)
            else:
                row.value = json.dumps(values, ensure_ascii=False)
            record_policy_update_events(
                db,
                policy_key=SENDER_WHITELIST_KEY,
                previous_values=previous_values,
                next_values=values,
                actor=current_user,
            )
            db.commit()
            db.refresh(row)
            return DomainListResponse(
                domains=values,
                updated_at=row.updated_at.isoformat() if row.updated_at else None,
            )

        db.execute(delete(SystemConfig).where(SystemConfig.key == SENDER_WHITELIST_KEY))
        record_policy_update_events(
            db,
            policy_key=SENDER_WHITELIST_KEY,
            previous_values=previous_values,
            next_values=[],
            actor=current_user,
        )
        db.commit()
    return DomainListResponse(domains=[], updated_at=None)


@router.get("/sender-blacklist", response_model=DomainListResponse)
def get_sender_blacklist(container: AppContainer = Depends(get_container)):
    values, updated_at = _load_sender_list(container, SENDER_BLACKLIST_KEY)
    return DomainListResponse(domains=values, updated_at=updated_at)


@router.put("/sender-blacklist", response_model=DomainListResponse)
def update_sender_blacklist(
    payload: DomainListUpdateRequest,
    container: AppContainer = Depends(get_container),
    current_user: str = Depends(get_current_user),
):
    values = _normalize_sender_list(payload.domains)
    previous_values = _get_current_values(container, SENDER_BLACKLIST_KEY, sender_mode=True)
    with container.analysis_service.session_factory() as db:
        if values:
            row = db.get(SystemConfig, SENDER_BLACKLIST_KEY)
            if row is None:
                row = SystemConfig(key=SENDER_BLACKLIST_KEY, value=json.dumps(values, ensure_ascii=False))
                db.add(row)
            else:
                row.value = json.dumps(values, ensure_ascii=False)
            record_policy_update_events(
                db,
                policy_key=SENDER_BLACKLIST_KEY,
                previous_values=previous_values,
                next_values=values,
                actor=current_user,
            )
            db.commit()
            db.refresh(row)
            return DomainListResponse(
                domains=values,
                updated_at=row.updated_at.isoformat() if row.updated_at else None,
            )

        db.execute(delete(SystemConfig).where(SystemConfig.key == SENDER_BLACKLIST_KEY))
        record_policy_update_events(
            db,
            policy_key=SENDER_BLACKLIST_KEY,
            previous_values=previous_values,
            next_values=[],
            actor=current_user,
        )
        db.commit()
    return DomainListResponse(domains=[], updated_at=None)


@router.get("/domain-blacklist", response_model=DomainListResponse)
def get_domain_blacklist(container: AppContainer = Depends(get_container)):
    domains, updated_at = _load_domain_list(container, DOMAIN_BLACKLIST_KEY)
    return DomainListResponse(domains=domains, updated_at=updated_at)


@router.put("/domain-blacklist", response_model=DomainListResponse)
def update_domain_blacklist(
    payload: DomainListUpdateRequest,
    container: AppContainer = Depends(get_container),
    current_user: str = Depends(get_current_user),
):
    domains = _normalize_domain_list(payload.domains)
    previous_values = _get_current_values(container, DOMAIN_BLACKLIST_KEY, sender_mode=False)
    with container.analysis_service.session_factory() as db:
        if domains:
            row = db.get(SystemConfig, DOMAIN_BLACKLIST_KEY)
            if row is None:
                row = SystemConfig(key=DOMAIN_BLACKLIST_KEY, value=json.dumps(domains, ensure_ascii=False))
                db.add(row)
            else:
                row.value = json.dumps(domains, ensure_ascii=False)
            record_policy_update_events(
                db,
                policy_key=DOMAIN_BLACKLIST_KEY,
                previous_values=previous_values,
                next_values=domains,
                actor=current_user,
            )
            db.commit()
            db.refresh(row)
            return DomainListResponse(
                domains=domains,
                updated_at=row.updated_at.isoformat() if row.updated_at else None,
            )

        db.execute(delete(SystemConfig).where(SystemConfig.key == DOMAIN_BLACKLIST_KEY))
        record_policy_update_events(
            db,
            policy_key=DOMAIN_BLACKLIST_KEY,
            previous_values=previous_values,
            next_values=[],
            actor=current_user,
        )
        db.commit()
    return DomainListResponse(domains=[], updated_at=None)


@router.get("/policy-summary", response_model=PolicySummaryResponse)
def get_policy_summary(container: AppContainer = Depends(get_container)):
    current_policies = {
        SENDER_WHITELIST_KEY: _get_current_values(container, SENDER_WHITELIST_KEY, sender_mode=True),
        SENDER_BLACKLIST_KEY: _get_current_values(container, SENDER_BLACKLIST_KEY, sender_mode=True),
        DOMAIN_BLACKLIST_KEY: _get_current_values(container, DOMAIN_BLACKLIST_KEY, sender_mode=False),
    }
    with container.analysis_service.session_factory() as db:
        summary = build_policy_summary(db, current_policies=current_policies)
    return PolicySummaryResponse(**summary)


@router.get("/policy-events", response_model=PolicyEventListResponse)
def get_policy_events(
    limit: int = Query(default=30, ge=1, le=200),
    container: AppContainer = Depends(get_container),
):
    with container.analysis_service.session_factory() as db:
        events = list_recent_policy_events(db, limit=limit)
    return PolicyEventListResponse(
        items=[
            PolicyEventResponse(
                id=item.id,
                event_type=item.event_type,
                policy_key=item.policy_key,
                policy_value=item.policy_value,
                action=item.action,
                actor=item.actor,
                analysis_id=item.analysis_id,
                created_at=item.created_at.isoformat(),
            )
            for item in events
        ]
    )
