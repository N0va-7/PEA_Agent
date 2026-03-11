from pathlib import Path

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
    monkeypatch.setenv("MODEL_DIR", str(Path(__file__).resolve().parents[2] / "ml" / "artifacts"))
    monkeypatch.setenv("VT_ENABLED", "true")
    monkeypatch.setenv("VT_API_KEY", "test-key")


def _auth_headers(client: TestClient):
    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class _FakeUrlModel:
    classes_ = ["benign", "phishing"]

    def predict_proba(self, _items):
        return [[0.08, 0.92]]


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_url_checks_create_and_reuse_existing_record(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    from backend.main import create_app

    monkeypatch.setattr("backend.agent_tools.url_model_analysis._load_url_model", lambda _path: _FakeUrlModel())
    vt_calls = {"count": 0}

    def fake_get(*_args, **_kwargs):
        vt_calls["count"] += 1
        return _Response(
            200,
            {"data": {"attributes": {"reputation": -20, "last_analysis_stats": {"malicious": 1, "suspicious": 0, "harmless": 1}}}},
        )

    monkeypatch.setattr("backend.agent_tools.url_reputation_vt.requests.get", fake_get)

    app = create_app()
    with TestClient(app) as client:
        headers = _auth_headers(client)

        first = client.post(
            "/api/v1/url-checks",
            json={"urls": ["https://evil.example.com/login"]},
            headers=headers,
        )
        assert first.status_code == 200
        first_payload = first.json()
        assert first_payload["created_count"] == 1
        assert first_payload["reused_count"] == 0
        assert first_payload["items"][0]["decision"]["verdict"] == "malicious"
        assert first_payload["items"][0]["decision"]["primary_risk_source"] == "vt_url_reputation"
        assert first_payload["items"][0]["is_cached_result"] is False

        second = client.post(
            "/api/v1/url-checks",
            json={"urls": ["HTTPS://EVIL.EXAMPLE.COM/login"]},
            headers=headers,
        )
        assert second.status_code == 200
        second_payload = second.json()
        assert second_payload["created_count"] == 0
        assert second_payload["reused_count"] == 1
        assert second_payload["items"][0]["is_cached_result"] is True
        assert second_payload["items"][0]["request_count"] == 2

        listing = client.get("/api/v1/url-checks?page=1&page_size=10", headers=headers)
        assert listing.status_code == 200
        list_payload = listing.json()
        assert list_payload["total"] == 1
        assert list_payload["items"][0]["normalized_url"] == "https://evil.example.com/login"

    assert vt_calls["count"] == 1


def test_url_checks_reject_invalid_urls(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    from backend.main import create_app

    app = create_app()
    with TestClient(app) as client:
        headers = _auth_headers(client)
        res = client.post("/api/v1/url-checks", json={"urls": ["not-a-url"]}, headers=headers)
        assert res.status_code == 400
        assert res.json()["code"] == "invalid_url"
