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
