from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient


def _set_env(monkeypatch, tmp_path):
    sqlite_path = tmp_path / 'analysis.db'
    monkeypatch.setenv('AUTH_USERNAME', 'admin')
    monkeypatch.setenv('AUTH_PASSWORD_HASH', '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9')
    monkeypatch.setenv('LLM_API_KEY', 'dummy-key')
    monkeypatch.setenv('LLM_BASE_URL', 'https://api.openai.com/v1')
    monkeypatch.setenv('LLM_MODEL_ID', 'gpt-4o-mini')
    monkeypatch.setenv('JWT_SECRET_KEY', 'test-secret-key')
    monkeypatch.setenv('SQLITE_DB_PATH', str(sqlite_path))
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{sqlite_path}')
    monkeypatch.setenv('REPORT_OUTPUT_DIR', str(tmp_path / 'reports'))
    monkeypatch.setenv('UPLOAD_DIR', str(tmp_path / 'uploads'))
    monkeypatch.setenv('MODEL_DIR', str(Path(__file__).resolve().parents[2] / 'ml' / 'artifacts'))


def _auth_headers(client: TestClient):
    login = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'admin123'})
    assert login.status_code == 200
    token = login.json()['access_token']
    return {'Authorization': f'Bearer {token}'}


def test_jobs_status_contains_progress_events(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    from backend.main import create_app

    app = create_app()
    container = app.state.container
    with container.analysis_service.session_factory() as db:
        container.analysis_service.job_repo.create(
            db,
            'job-1',
            current_stage='queued',
            progress_events=[
                {
                    'seq': 1,
                    'type': 'job_queued',
                    'status': 'queued',
                    'stage': 'queued',
                    'stage_label': '已入队',
                    'message': '任务已入队，等待执行',
                    'at': datetime.now(timezone.utc).isoformat(),
                }
            ],
        )
        container.analysis_service.job_repo.mark_running(db, 'job-1')
        container.analysis_service.job_repo.append_progress_event(
            db,
            'job-1',
            {
                'type': 'stage_done',
                'status': 'running',
                'stage': 'email_parser',
                'stage_label': '邮件解析',
                'message': '执行完成：邮件解析',
                'at': datetime.now(timezone.utc).isoformat(),
            },
            current_stage='email_parser',
        )

    with TestClient(app) as client:
        headers = _auth_headers(client)
        res = client.get('/api/v1/jobs/job-1', headers=headers)
        assert res.status_code == 200
        payload = res.json()
        assert payload['id'] == 'job-1'
        assert payload['current_stage'] == 'email_parser'
        assert len(payload['progress_events']) >= 2


def test_reports_download_stream(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    from backend.main import create_app

    app = create_app()
    container = app.state.container
    reports_dir = tmp_path / 'reports'
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / 'report_a1.md'
    report_path.write_text('# report-a1', encoding='utf-8')

    with container.analysis_service.session_factory() as db:
        container.analysis_service.analysis_repo.create(
            db,
            {
                'id': 'a1',
                'message_id': 'm1',
                'fingerprint': 'f1',
                'sender': 's@example.com',
                'recipient': 'r@example.com',
                'subject': 'subject',
                'parsed_email': {'message_id': 'm1', 'sender': 's@example.com', 'recipient': 'r@example.com', 'subject': 'subject', 'attachments': []},
                'url_extraction': {'normalized_urls': []},
                'url_reputation': {'items': [], 'high_risk_urls': [], 'summary': 'none'},
                'url_analysis': {},
                'content_review': {},
                'attachment_analysis': {},
                'decision': {'verdict': 'benign'},
                'report_markdown': '# report-a1',
                'report_path': str(report_path),
                'execution_trace': [],
                'created_at': datetime.now(timezone.utc),
            },
        )

    with TestClient(app) as client:
        headers = _auth_headers(client)
        res = client.get('/api/v1/reports/a1', headers=headers)
        assert res.status_code == 200
        assert res.text.startswith('# report-a1')
