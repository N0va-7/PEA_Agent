from __future__ import annotations

import base64
import hashlib
import json
import threading
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import requests
from sqlalchemy import select

from backend.agent_tools.base import AnalysisTool
from backend.infra.config import Settings
from backend.models.tables import VTUrlCache


class _PublicApiLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._last_request_at = 0.0
        self._day_key = ""
        self._day_count = 0

    def acquire(self, *, min_interval_seconds: int, daily_budget: int) -> bool:
        with self._lock:
            now = datetime.now(UTC)
            day_key = now.strftime("%Y-%m-%d")
            if self._day_key != day_key:
                self._day_key = day_key
                self._day_count = 0
            if self._day_count >= daily_budget:
                return False
            wait_seconds = max(0.0, min_interval_seconds - (time.monotonic() - self._last_request_at))
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            self._last_request_at = time.monotonic()
            self._day_count += 1
            return True


_VT_LIMITER = _PublicApiLimiter()


def _clip01(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed != parsed:
        return default
    return min(1.0, max(0.0, parsed))


def _url_to_vt_id(url: str) -> str:
    encoded = base64.urlsafe_b64encode(url.encode("utf-8")).decode("ascii")
    return encoded.rstrip("=")


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _parse_vt_payload(url: str, url_id: str, payload: dict[str, Any] | None, *, cache_status: str) -> dict[str, Any]:
    payload = payload or {}
    attributes = ((payload.get("data") or {}).get("attributes") or {}) if payload else {}
    stats = attributes.get("last_analysis_stats") or {}
    harmless = int(stats.get("harmless") or 0)
    malicious = int(stats.get("malicious") or 0)
    suspicious = int(stats.get("suspicious") or 0)
    reputation = int(attributes.get("reputation") or 0)

    risk_score = 0.0
    if malicious > 0:
        risk_score = 1.0
    elif suspicious > 1:
        risk_score = 0.8
    elif suspicious > 0:
        risk_score = 0.55
    elif reputation < 0:
        risk_score = min(0.75, abs(reputation) / 100.0)
    elif harmless > 0:
        risk_score = 0.05

    is_high_risk = malicious > 0 or suspicious >= 2
    if is_high_risk:
        risk_level = "high"
    elif suspicious > 0 or reputation < 0:
        risk_level = "medium"
    elif payload:
        risk_level = "low"
    else:
        risk_level = "unknown"

    categories = attributes.get("categories")
    if isinstance(categories, dict):
        categories = sorted({str(item).strip() for item in categories.values() if str(item).strip()})
    elif isinstance(categories, list):
        categories = [str(item).strip() for item in categories if str(item).strip()]
    else:
        categories = []

    tags = [str(item).strip() for item in (attributes.get("tags") or []) if str(item).strip()]
    summary_bits = []
    if is_high_risk:
        summary_bits.append("VT 明确高危")
    elif risk_level == "medium":
        summary_bits.append("VT 存在可疑信号")
    elif payload:
        summary_bits.append("VT 未发现高危")
    else:
        summary_bits.append("VT 无记录或未查询")
    summary_bits.append(f"malicious={malicious}")
    summary_bits.append(f"suspicious={suspicious}")

    return {
        "url": url,
        "url_id": url_id,
        "vt_found": bool(payload),
        "reputation": reputation,
        "last_analysis_stats": {
            "harmless": harmless,
            "malicious": malicious,
            "suspicious": suspicious,
        },
        "categories": categories,
        "tags": tags,
        "source": "virustotal",
        "cache_status": cache_status,
        "risk_level": risk_level,
        "risk_score": round(_clip01(risk_score), 6),
        "is_high_risk": is_high_risk,
        "summary": " / ".join(summary_bits),
    }


def make_url_reputation_vt_tool(settings: Settings, session_factory) -> AnalysisTool:
    def fetch_cached(normalized_url: str) -> VTUrlCache | None:
        url_hash = _url_hash(normalized_url)
        with session_factory() as db:
            stmt = select(VTUrlCache).where(VTUrlCache.url_hash == url_hash).limit(1)
            return db.execute(stmt).scalar_one_or_none()

    def store_cache(normalized_url: str, url_id: str, payload_json: dict[str, Any] | None, http_status: int):
        url_hash = _url_hash(normalized_url)
        now = datetime.now(UTC)
        expires_at = now + timedelta(hours=max(1, settings.vt_cache_ttl_hours))
        encoded = json.dumps(payload_json or {}, ensure_ascii=False)
        with session_factory() as db:
            row = db.execute(select(VTUrlCache).where(VTUrlCache.url_hash == url_hash).limit(1)).scalar_one_or_none()
            if row is None:
                row = VTUrlCache(
                    url_hash=url_hash,
                    normalized_url=normalized_url,
                    vt_url_id=url_id,
                    payload_json=encoded,
                    fetched_at=now,
                    expires_at=expires_at,
                    http_status=http_status,
                )
                db.add(row)
            else:
                row.normalized_url = normalized_url
                row.vt_url_id = url_id
                row.payload_json = encoded
                row.fetched_at = now
                row.expires_at = expires_at
                row.http_status = http_status
            db.commit()

    def request_vt(normalized_url: str) -> tuple[int, dict[str, Any] | None, str]:
        if not settings.vt_enabled or not settings.vt_api_key:
            return 0, None, "disabled"

        allowed = _VT_LIMITER.acquire(
            min_interval_seconds=max(1, settings.vt_min_interval_seconds),
            daily_budget=max(1, settings.vt_daily_budget),
        )
        if not allowed:
            return 0, None, "daily_budget_exhausted"

        url_id = _url_to_vt_id(normalized_url)
        headers = {"x-apikey": settings.vt_api_key}
        try:
            response = requests.get(
                f"{settings.vt_base_url.rstrip('/')}/urls/{url_id}",
                headers=headers,
                timeout=max(1, settings.vt_timeout_seconds),
            )
        except requests.RequestException:
            return 0, None, "request_error"
        try:
            payload = response.json()
        except ValueError:
            payload = None
        return response.status_code, payload, "live"

    def runner(context: dict[str, Any]) -> dict[str, Any]:
        extraction = context.get("url_extraction", {}) or {}
        normalized_urls = list(dict.fromkeys(str(item) for item in extraction.get("normalized_urls", []) if str(item)))
        items: list[dict[str, Any]] = []
        high_risk_urls: list[str] = []
        queried_count = 0
        skipped_count = 0

        for normalized_url in normalized_urls:
            cached = fetch_cached(normalized_url)
            url_id = _url_to_vt_id(normalized_url)
            cached_expires_at = _as_utc(getattr(cached, "expires_at", None))
            if cached and cached_expires_at and cached_expires_at >= datetime.now(UTC):
                payload = {}
                try:
                    payload = json.loads(cached.payload_json or "{}")
                except ValueError:
                    payload = {}
                item = _parse_vt_payload(normalized_url, cached.vt_url_id or url_id, payload, cache_status="hit")
                items.append(item)
                if item["is_high_risk"]:
                    high_risk_urls.append(normalized_url)
                skipped_count += 1
                continue

            status_code, payload, source_state = request_vt(normalized_url)
            if status_code in {200, 404}:
                store_cache(normalized_url, url_id, payload if status_code == 200 else {}, status_code)
            elif cached and cached.http_status == 200:
                try:
                    payload = json.loads(cached.payload_json or "{}")
                except ValueError:
                    payload = {}
                item = _parse_vt_payload(normalized_url, cached.vt_url_id or url_id, payload, cache_status="stale_hit")
                items.append(item)
                if item["is_high_risk"]:
                    high_risk_urls.append(normalized_url)
                queried_count += 1
                continue

            cache_status = "miss" if source_state == "live" else source_state
            item = _parse_vt_payload(
                normalized_url,
                url_id,
                payload if status_code == 200 else None,
                cache_status=cache_status,
            )
            if status_code == 404:
                item["summary"] = "VT 无记录"
            elif status_code in {429, 503, 504}:
                item["summary"] = "VT 暂不可用，已降级继续"
                item["cache_status"] = "degraded"
            elif not settings.vt_enabled or not settings.vt_api_key:
                item["summary"] = "VT 未启用"
            items.append(item)
            if item["is_high_risk"]:
                high_risk_urls.append(normalized_url)
            queried_count += 1

        max_risk_score = max((float(item.get("risk_score") or 0.0) for item in items), default=0.0)
        summary = "未发现 URL" if not items else (
            "存在 VT 高危 URL" if high_risk_urls else "VT 未发现直接高危 URL"
        )
        return {
            "url_reputation": {
                "items": items,
                "max_risk_score": round(_clip01(max_risk_score), 6),
                "high_risk_urls": high_risk_urls,
                "queried_count": queried_count,
                "skipped_count": skipped_count,
                "summary": summary,
            }
        }

    return AnalysisTool(
        tool_name="url_reputation_vt",
        version="1.0.0",
        input_schema={"url_extraction": "dict"},
        output_schema={"url_reputation": "dict"},
        runner=runner,
    )
