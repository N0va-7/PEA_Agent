from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient


def _set_env(monkeypatch, tmp_path):
    monkeypatch.setenv('AUTH_USERNAME', 'admin')
    monkeypatch.setenv('AUTH_PASSWORD_HASH', '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9')
    monkeypatch.setenv('LLM_API_KEY', 'dummy-key')
    monkeypatch.setenv('LLM_BASE_URL', 'https://api.openai.com/v1')
    monkeypatch.setenv('LLM_MODEL_ID', 'gpt-4o-mini')
    monkeypatch.setenv('JWT_SECRET_KEY', 'test-secret-key')
    monkeypatch.setenv('SQLITE_DB_PATH', str(tmp_path / 'analysis.db'))
    monkeypatch.setenv('REPORT_OUTPUT_DIR', str(tmp_path / 'reports'))
    monkeypatch.setenv('UPLOAD_DIR', str(tmp_path / 'uploads'))
    monkeypatch.setenv('MODEL_DIR', str(Path(__file__).resolve().parents[2] / 'ml' / 'artifacts'))


def _auth_headers(client: TestClient):
    login = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'admin123'})
    assert login.status_code == 200
    token = login.json()['access_token']
    return {'Authorization': f'Bearer {token}'}


def test_invalid_created_from_returns_400(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    from backend.main import create_app

    app = create_app()
    with TestClient(app) as client:
        headers = _auth_headers(client)
        res = client.get('/api/v1/analyses?created_from=not-a-date', headers=headers)
        assert res.status_code == 400
        payload = res.json()
        assert payload['code'] == 'invalid_datetime'


def test_invalid_sort_by_returns_400(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    from backend.main import create_app

    app = create_app()
    with TestClient(app) as client:
        headers = _auth_headers(client)
        res = client.get('/api/v1/analyses?sort_by=unknown', headers=headers)
        assert res.status_code == 400
        assert res.json()['code'] == 'invalid_sort_by'


def test_non_eml_upload_returns_400(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    from backend.main import create_app

    app = create_app()
    with TestClient(app) as client:
        headers = _auth_headers(client)
        files = {'file': ('sample.txt', b'hello', 'text/plain')}
        res = client.post('/api/v1/analyses', files=files, headers=headers)
        assert res.status_code == 400
        assert res.json()['code'] == 'invalid_file_type'


def test_list_analyses_pagination_and_sort(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    from backend.main import create_app

    app = create_app()
    container = app.state.container
    reports_dir = tmp_path / 'reports'
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / 'r1.md').write_text('r1', encoding='utf-8')
    (reports_dir / 'r2.md').write_text('r2', encoding='utf-8')

    with container.analysis_service.session_factory() as db:
        container.analysis_service.analysis_repo.create(
            db,
            {
                'id': 'a1',
                'message_id': 'm1',
                'fingerprint': 'f1',
                'sender': 'z@example.com',
                'recipient': 'r@example.com',
                'subject': 'Subject Z',
                'url_analysis': {},
                'body_analysis': {},
                'attachment_analysis': {},
                'final_decision': {'is_malicious': True},
                'llm_report': '# r1',
                'report_path': str(reports_dir / 'r1.md'),
                'execution_trace': [],
                'created_at': datetime(2026, 2, 21, 9, 0, tzinfo=timezone.utc),
            },
        )
        container.analysis_service.analysis_repo.create(
            db,
            {
                'id': 'a2',
                'message_id': 'm2',
                'fingerprint': 'f2',
                'sender': 'a@example.com',
                'recipient': 'r@example.com',
                'subject': 'Subject A',
                'url_analysis': {},
                'body_analysis': {},
                'attachment_analysis': {},
                'final_decision': {'is_malicious': False},
                'llm_report': '# r2',
                'report_path': str(reports_dir / 'r2.md'),
                'execution_trace': [],
                'created_at': datetime(2026, 2, 21, 10, 0, tzinfo=timezone.utc),
            },
        )

    with TestClient(app) as client:
        headers = _auth_headers(client)
        res = client.get('/api/v1/analyses?page=1&page_size=1&sort_by=sender&sort_order=asc', headers=headers)
        assert res.status_code == 200
        payload = res.json()
        assert payload['total'] == 2
        assert payload['page'] == 1
        assert payload['page_size'] == 1
        assert payload['sort_by'] == 'sender'
        assert payload['sort_order'] == 'asc'
        assert len(payload['items']) == 1
        assert payload['items'][0]['id'] == 'a2'
