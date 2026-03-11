from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.models.tables import AnalysisFeedbackEvent, EmailAnalysis


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


def _auth_headers(client: TestClient):
    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_analysis(container, *, analysis_id: str, report_path: Path):
    with container.analysis_service.session_factory() as db:
        container.analysis_service.analysis_repo.create(
            db,
            {
                "id": analysis_id,
                "message_id": f"m-{analysis_id}",
                "fingerprint": f"f-{analysis_id}",
                "sender": "s@example.com",
                "recipient": "r@example.com",
                "subject": analysis_id,
                "parsed_email": {"message_id": f"m-{analysis_id}", "sender": "s@example.com", "recipient": "r@example.com", "subject": analysis_id, "attachments": []},
                "url_extraction": {"normalized_urls": []},
                "url_reputation": {"items": [], "high_risk_urls": [], "summary": "none"},
                "url_analysis": {},
                "content_review": {},
                "attachment_analysis": {},
                "decision": {"verdict": "benign"},
                "report_markdown": f"# {analysis_id}",
                "report_path": str(report_path),
                "execution_trace": [],
                "created_at": datetime.now(timezone.utc),
            },
        )


def test_report_path_fallback_by_filename(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    from backend.main import create_app

    app = create_app()
    container = app.state.container
    report_root = tmp_path / "reports"
    report_root.mkdir(parents=True, exist_ok=True)

    valid_file = report_root / "report_a1.md"
    valid_file.write_text("# fallback report", encoding="utf-8")

    legacy_path = tmp_path / "legacy" / "report_a1.md"
    _seed_analysis(container, analysis_id="a1", report_path=legacy_path)

    with TestClient(app) as client:
        headers = _auth_headers(client)
        res = client.get("/api/v1/reports/a1", headers=headers)
        assert res.status_code == 200
        assert res.text.startswith("# fallback report")


def test_delete_single_and_clear_history(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    from backend.main import create_app

    app = create_app()
    container = app.state.container
    report_root = tmp_path / "reports"
    report_root.mkdir(parents=True, exist_ok=True)

    r1 = report_root / "report_a1.md"
    r2 = report_root / "report_a2.md"
    r1.write_text("# a1", encoding="utf-8")
    r2.write_text("# a2", encoding="utf-8")
    _seed_analysis(container, analysis_id="a1", report_path=r1)
    _seed_analysis(container, analysis_id="a2", report_path=r2)
    with container.analysis_service.session_factory() as db:
        db.add(
            AnalysisFeedbackEvent(
                id="fb-1",
                analysis_id="a1",
                old_review_label=None,
                new_review_label="malicious",
                old_review_note=None,
                new_review_note="seed",
                changed_by="seed",
                changed_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

    with TestClient(app) as client:
        headers = _auth_headers(client)
        delete_one = client.delete("/api/v1/analyses/a1", headers=headers)
        assert delete_one.status_code == 200
        assert delete_one.json()["deleted_count"] == 1

        clear_all = client.delete("/api/v1/analyses", headers=headers)
        assert clear_all.status_code == 200
        assert clear_all.json()["deleted_count"] == 1

    with container.analysis_service.session_factory() as db:
        left = db.execute(select(func.count()).select_from(EmailAnalysis)).scalar_one()
        feedback_left = db.execute(select(func.count()).select_from(AnalysisFeedbackEvent)).scalar_one()
        assert int(left) == 0
        assert int(feedback_left) == 0
    assert not r1.exists()
    assert not r2.exists()
