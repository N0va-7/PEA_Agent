from datetime import UTC, datetime, timedelta
import json

from backend.agent_tools.url_reputation_vt import make_url_reputation_vt_tool
from backend.infra.config import Settings
from backend.infra.db import create_engine_and_session, init_db
from backend.models.tables import VTUrlCache


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def _settings(tmp_path):
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'analysis.db'}",
        sqlite_db_path=tmp_path / "analysis.db",
        report_output_dir=tmp_path / "reports",
        upload_dir=tmp_path / "uploads",
        model_dir=tmp_path,
        llm_api_key="",
        llm_base_url="https://api.openai.com/v1",
        llm_model_id="gpt-4o-mini",
        vt_api_key="test-key",
        vt_base_url="https://www.virustotal.com/api/v3",
        vt_enabled=True,
        vt_public_mode=True,
        vt_cache_ttl_hours=24,
        vt_min_interval_seconds=1,
        vt_daily_budget=500,
        vt_timeout_seconds=20,
        attachment_sandbox_base_url="",
        attachment_sandbox_source_id="pea-agent",
        attachment_sandbox_timeout_seconds=45,
        attachment_sandbox_poll_interval_seconds=2,
        jwt_secret_key="secret",
        jwt_algorithm="HS256",
        jwt_expire_hours=8,
        cors_allow_origins=["http://localhost:5173"],
        auth_username="admin",
        auth_password_hash="x",
        job_queue_backend="memory",
        redis_url="",
        redis_queue_name="pea:jobs",
        upload_retention_hours=72,
        login_rate_max_attempts=10,
        login_rate_window_seconds=300,
        expose_internal_error_details=False,
    )


def test_url_reputation_uses_cache_without_network(monkeypatch, tmp_path):
    settings = _settings(tmp_path)
    engine, session_factory = create_engine_and_session(settings.sqlite_db_path)
    init_db(engine)
    with session_factory() as db:
        db.add(
            VTUrlCache(
                url_hash="cache-key",
                normalized_url="https://cached.test/login",
                vt_url_id="cached-id",
                payload_json=json.dumps(
                    {"data": {"attributes": {"reputation": 0, "last_analysis_stats": {"malicious": 1, "suspicious": 0, "harmless": 10}}}}
                ),
                fetched_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                http_status=200,
            )
        )
        db.commit()

    from backend.agent_tools import url_reputation_vt as module

    monkeypatch.setattr(module, "_url_hash", lambda _url: "cache-key")
    monkeypatch.setattr(module.requests, "get", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network should not be called")))

    tool = make_url_reputation_vt_tool(settings, session_factory)
    out = tool.run({"url_extraction": {"normalized_urls": ["https://cached.test/login"]}})

    item = out["url_reputation"]["items"][0]
    assert item["cache_status"] == "hit"
    assert item["is_high_risk"] is True


def test_url_reputation_marks_live_malicious_urls_as_high_risk(monkeypatch, tmp_path):
    settings = _settings(tmp_path)
    engine, session_factory = create_engine_and_session(settings.sqlite_db_path)
    init_db(engine)

    monkeypatch.setattr(
        "backend.agent_tools.url_reputation_vt.requests.get",
        lambda *args, **kwargs: _Response(
            200,
            {"data": {"attributes": {"reputation": -10, "last_analysis_stats": {"malicious": 2, "suspicious": 0, "harmless": 1}}}},
        ),
    )

    tool = make_url_reputation_vt_tool(settings, session_factory)
    out = tool.run({"url_extraction": {"normalized_urls": ["https://evil.test/login"]}})

    reputation = out["url_reputation"]
    assert reputation["high_risk_urls"] == ["https://evil.test/login"]
    assert reputation["items"][0]["cache_status"] == "miss"
    assert reputation["items"][0]["is_high_risk"] is True
