from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.models.tables import SystemConfig


def _set_env(monkeypatch, tmp_path, *, min_total=500, min_class=100, recent_days=7):
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
    monkeypatch.setenv("TUNING_MIN_TOTAL_SAMPLES", str(min_total))
    monkeypatch.setenv("TUNING_MIN_CLASS_SAMPLES", str(min_class))
    monkeypatch.setenv("TUNING_RECENT_DAYS", str(recent_days))


def _auth_headers(client: TestClient):
    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_analysis(container, tmp_path, analysis_id: str, *, review_label=None, url_prob=0.0, text_prob=0.0):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"{analysis_id}.md"
    report_path.write_text(f"# {analysis_id}", encoding="utf-8")

    payload = {
        "id": analysis_id,
        "message_id": f"m-{analysis_id}",
        "fingerprint": f"f-{analysis_id}",
        "sender": "s@example.com",
        "recipient": "r@example.com",
        "subject": analysis_id,
        "url_analysis": {"max_possibility": url_prob},
        "body_analysis": {"phishing_probability": text_prob},
        "attachment_analysis": {},
        "final_decision": {"is_malicious": False},
        "llm_report": f"# {analysis_id}",
        "report_path": str(report_path),
        "execution_trace": [],
        "created_at": datetime.now(timezone.utc),
    }
    if review_label is not None:
        payload["review_label"] = review_label
        payload["reviewed_by"] = "seed"
        payload["reviewed_at"] = datetime.now(timezone.utc)
    with container.analysis_service.session_factory() as db:
        container.analysis_service.analysis_repo.create(db, payload)


def test_feedback_upsert_and_history(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    from backend.main import create_app

    app = create_app()
    container = app.state.container
    _seed_analysis(container, tmp_path, "a1")

    with TestClient(app) as client:
        headers = _auth_headers(client)
        res = client.post(
            "/api/v1/analyses/a1/feedback",
            json={"review_label": "malicious", "review_note": "looks bad"},
            headers=headers,
        )
        assert res.status_code == 200
        body = res.json()
        assert body["review_label"] == "malicious"
        assert body["reviewed_by"] == "admin"

        get_analysis = client.get("/api/v1/analyses/a1", headers=headers)
        assert get_analysis.status_code == 200
        assert get_analysis.json()["review_label"] == "malicious"

        history = client.get("/api/v1/analyses/a1/feedback-history", headers=headers)
        assert history.status_code == 200
        rows = history.json()
        assert len(rows) == 1
        assert rows[0]["old_review_label"] is None
        assert rows[0]["new_review_label"] == "malicious"


def test_tuning_precheck_run_and_activate(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path, min_total=3, min_class=1, recent_days=30)
    from backend.main import create_app

    app = create_app()
    container = app.state.container
    _seed_analysis(container, tmp_path, "a1", review_label="malicious", url_prob=0.95, text_prob=0.92)
    _seed_analysis(container, tmp_path, "a2", review_label="benign", url_prob=0.10, text_prob=0.20)
    _seed_analysis(container, tmp_path, "a3", review_label="benign", url_prob=0.15, text_prob=0.25)

    with TestClient(app) as client:
        headers = _auth_headers(client)
        precheck = client.post("/api/v1/tuning/fusion/precheck", json={}, headers=headers)
        assert precheck.status_code == 200
        pre = precheck.json()
        assert pre["meets_requirements"] is True
        assert pre["valid_rows"] == 3

        not_confirmed = client.post("/api/v1/tuning/fusion/run", json={"confirm": False}, headers=headers)
        assert not_confirmed.status_code == 400
        assert not_confirmed.json()["code"] == "confirm_required"

        run = client.post(
            "/api/v1/tuning/fusion/run",
            json={"confirm": True, "fpr_target": 0.5, "w_step": 0.5, "th_min": 0.4, "th_max": 0.9, "th_step": 0.1},
            headers=headers,
        )
        assert run.status_code == 200
        run_body = run.json()
        assert run_body["status"] == "succeeded"
        run_id = run_body["run_id"]

        run_list = client.get("/api/v1/tuning/fusion/runs", headers=headers)
        assert run_list.status_code == 200
        assert run_list.json()["items"][0]["id"] == run_id

        activate = client.post(f"/api/v1/tuning/fusion/runs/{run_id}/activate", headers=headers)
        assert activate.status_code == 200
        assert activate.json()["active_run_id"] == run_id

    with container.analysis_service.session_factory() as db:
        cfg = db.get(SystemConfig, "active_fusion_tuning_run_id")
        assert cfg is not None
        assert cfg.value == run_id


def test_tuning_precheck_gate_blocks_small_samples(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path, min_total=10, min_class=2, recent_days=30)
    from backend.main import create_app

    app = create_app()
    container = app.state.container
    _seed_analysis(container, tmp_path, "a1", review_label="malicious", url_prob=0.9, text_prob=0.9)
    _seed_analysis(container, tmp_path, "a2", review_label="benign", url_prob=0.1, text_prob=0.1)

    with TestClient(app) as client:
        headers = _auth_headers(client)
        run = client.post(
            "/api/v1/tuning/fusion/run",
            json={"confirm": True, "fpr_target": 0.5, "w_step": 0.5, "th_min": 0.4, "th_max": 0.9, "th_step": 0.1},
            headers=headers,
        )
        assert run.status_code == 400
        payload = run.json()
        assert payload["code"] == "precheck_failed"
        assert payload["detail"]["meets_requirements"] is False
