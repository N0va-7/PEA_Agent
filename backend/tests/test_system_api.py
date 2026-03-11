from fastapi.testclient import TestClient


def _set_env(monkeypatch, tmp_path):
    sqlite_path = tmp_path / "analysis.db"
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD_HASH", "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9")
    monkeypatch.setenv("LLM_API_KEY", "dummy-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("LLM_MODEL_ID", "gpt-4o-mini")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("SQLITE_DB_PATH", str(sqlite_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{sqlite_path}")
    monkeypatch.setenv("REPORT_OUTPUT_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("MODEL_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("JOB_QUEUE_BACKEND", "memory")
    monkeypatch.setenv("REDIS_URL", "redis://user:secret-pass@127.0.0.1:6379/2")


def _auth_headers(client: TestClient):
    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_runtime_info_endpoint_masks_sensitive_values(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    from backend.main import create_app

    app = create_app()
    with TestClient(app) as client:
        headers = _auth_headers(client)
        res = client.get("/api/v1/system/runtime-info", headers=headers)
        assert res.status_code == 200
        payload = res.json()
        assert payload["database"]["driver"].startswith("sqlite")
        assert payload["database"]["has_password"] is False
        assert payload["queue"]["backend"] == "memory"
        assert "secret-pass" not in res.text


def test_safe_info_helpers_hide_password_in_display():
    from backend.api.routes.system import _safe_db_info, _safe_redis_info

    db_info = _safe_db_info("mysql+pymysql://root:root@127.0.0.1:3306/pea_agent?charset=utf8mb4")
    assert db_info["has_password"] is True
    assert "root:root" not in db_info["display"]

    redis_info = _safe_redis_info("redis://user:secret-pass@127.0.0.1:6379/2", "redis")
    assert redis_info["has_password"] is True
    assert "secret-pass" not in redis_info["display"]


def test_sender_whitelist_roundtrip(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    from backend.main import create_app

    app = create_app()
    with TestClient(app) as client:
        headers = _auth_headers(client)

        initial = client.get("/api/v1/system/sender-whitelist", headers=headers)
        assert initial.status_code == 200
        assert initial.json()["domains"] == []

        updated = client.put(
            "/api/v1/system/sender-whitelist",
            json={"domains": ["Alerts@example.com", "bad-value", "alerts@example.com"]},
            headers=headers,
        )
        assert updated.status_code == 200
        assert updated.json()["domains"] == ["alerts@example.com"]

        fetched = client.get("/api/v1/system/sender-whitelist", headers=headers)
        assert fetched.status_code == 200
        assert fetched.json()["domains"] == ["alerts@example.com"]


def test_domain_blacklist_roundtrip(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    from backend.main import create_app

    app = create_app()
    with TestClient(app) as client:
        headers = _auth_headers(client)

        updated = client.put(
            "/api/v1/system/domain-blacklist",
            json={"domains": ["Bad.Example.com", "phish@evil.test"]},
            headers=headers,
        )
        assert updated.status_code == 200
        assert updated.json()["domains"] == ["bad.example.com", "evil.test"]

        fetched = client.get("/api/v1/system/domain-blacklist", headers=headers)
        assert fetched.status_code == 200
        assert fetched.json()["domains"] == ["bad.example.com", "evil.test"]


def test_sender_blacklist_roundtrip(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    from backend.main import create_app

    app = create_app()
    with TestClient(app) as client:
        headers = _auth_headers(client)

        updated = client.put(
            "/api/v1/system/sender-blacklist",
            json={"domains": ["Bad.Actor@example.com", "bad.actor@example.com", "not-an-email"]},
            headers=headers,
        )
        assert updated.status_code == 200
        assert updated.json()["domains"] == ["bad.actor@example.com"]


def test_policy_summary_and_events_include_policy_updates(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    from backend.main import create_app

    app = create_app()
    with TestClient(app) as client:
        headers = _auth_headers(client)

        whitelist_update = client.put(
            "/api/v1/system/sender-whitelist",
            json={"domains": ["alerts@example.com"]},
            headers=headers,
        )
        assert whitelist_update.status_code == 200

        domain_update = client.put(
            "/api/v1/system/domain-blacklist",
            json={"domains": ["evil.test"]},
            headers=headers,
        )
        assert domain_update.status_code == 200

        summary = client.get("/api/v1/system/policy-summary", headers=headers)
        assert summary.status_code == 200
        payload = summary.json()
        assert payload["sender_whitelist"][0]["value"] == "alerts@example.com"
        assert payload["sender_whitelist"][0]["hit_count"] == 0
        assert payload["sender_whitelist"][0]["last_change_action"] == "added"
        assert payload["domain_blacklist"][0]["value"] == "evil.test"
        assert payload["domain_blacklist"][0]["last_change_action"] == "added"

        events = client.get("/api/v1/system/policy-events?limit=10", headers=headers)
        assert events.status_code == 200
        items = events.json()["items"]
        assert any(
            item["event_type"] == "policy_update"
            and item["policy_key"] == "sender_whitelist"
            and item["policy_value"] == "alerts@example.com"
            and item["actor"] == "admin"
            for item in items
        )
        assert any(
            item["event_type"] == "policy_update"
            and item["policy_key"] == "domain_blacklist"
            and item["policy_value"] == "evil.test"
            for item in items
        )
