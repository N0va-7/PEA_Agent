from fastapi.testclient import TestClient



def test_login_success_and_failure(monkeypatch):
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD_HASH", "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9")
    monkeypatch.setenv("LLM_API_KEY", "dummy-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("LLM_MODEL_ID", "gpt-4o-mini")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key")

    from backend.main import create_app

    app = create_app()
    client = TestClient(app)

    ok = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert ok.status_code == 200
    payload = ok.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]

    bad = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
    assert bad.status_code == 401
    assert bad.json()["code"] == "invalid_credentials"
