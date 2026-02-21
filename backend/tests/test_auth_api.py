from fastapi.testclient import TestClient



def test_login_success_and_failure(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./runtime/db/test_auth_api_1.db")
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


def test_login_rate_limit(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./runtime/db/test_auth_api_2.db")
    monkeypatch.setenv("AUTH_USERNAME", "admin_rate")
    monkeypatch.setenv("AUTH_PASSWORD_HASH", "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9")
    monkeypatch.setenv("LLM_API_KEY", "dummy-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("LLM_MODEL_ID", "gpt-4o-mini")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("LOGIN_RATE_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("LOGIN_RATE_WINDOW_SECONDS", "300")

    from backend.main import create_app

    app = create_app()
    client = TestClient(app)

    bad1 = client.post("/api/v1/auth/login", json={"username": "admin_rate", "password": "wrong"})
    assert bad1.status_code == 401

    bad2 = client.post("/api/v1/auth/login", json={"username": "admin_rate", "password": "wrong"})
    assert bad2.status_code == 401

    blocked = client.post("/api/v1/auth/login", json={"username": "admin_rate", "password": "wrong"})
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "too_many_login_attempts"


def test_login_supports_pbkdf2_hash(monkeypatch):
    from backend.infra.security import hash_password_pbkdf2

    monkeypatch.setenv("DATABASE_URL", "sqlite:///./runtime/db/test_auth_api_3.db")
    monkeypatch.setenv("AUTH_USERNAME", "admin_pbkdf2")
    monkeypatch.setenv("AUTH_PASSWORD_HASH", hash_password_pbkdf2("admin123", iterations=1000))
    monkeypatch.setenv("LLM_API_KEY", "dummy-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("LLM_MODEL_ID", "gpt-4o-mini")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key")

    from backend.main import create_app

    app = create_app()
    client = TestClient(app)

    ok = client.post("/api/v1/auth/login", json={"username": "admin_pbkdf2", "password": "admin123"})
    assert ok.status_code == 200
    assert ok.json()["access_token"]
