from backend.infra.config import Settings
from backend.infra.db import create_engine_and_session, init_db
from backend.infra.report_store import ReportStore
from backend.repositories.analysis_repo import AnalysisRepository
from backend.repositories.job_repo import JobRepository
from backend.services.analysis_service import AnalysisService


class DummyGraph:
    def __init__(self, result):
        self._result = result

    def invoke(self, _state, config=None):
        return self._result


class StreamingGraph:
    def stream(self, _state, config=None):
        yield {"fingerprint_email": {"analysis_id": "a-2"}}
        yield {"check_existing_analysis": {"is_cached_result": True, "analysis_id": "a-2"}}



def _build_settings(tmp_path):
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'analysis.db'}",
        sqlite_db_path=tmp_path / "analysis.db",
        report_output_dir=tmp_path / "reports",
        upload_dir=tmp_path / "uploads",
        model_dir=tmp_path,
        llm_api_key="",
        llm_base_url="https://api.openai.com/v1",
        llm_model_id="gpt-4o-mini",
        threatbook_api_key="",
        jwt_secret_key="secret",
        jwt_algorithm="HS256",
        jwt_expire_hours=8,
        cors_allow_origins=["http://localhost:5173"],
        auth_username="admin",
        auth_password_hash="x",
        tuning_min_total_samples=500,
        tuning_min_class_samples=100,
        tuning_recent_days=7,
        job_queue_backend="memory",
        redis_url="",
        redis_queue_name="pea:jobs",
        upload_retention_hours=72,
        login_rate_max_attempts=10,
        login_rate_window_seconds=300,
        expose_internal_error_details=False,
    )



def test_process_job_marks_cached(monkeypatch, tmp_path):
    settings = _build_settings(tmp_path)
    engine, session_factory = create_engine_and_session(settings.sqlite_db_path)
    init_db(engine)

    monkeypatch.setattr(
        "backend.services.analysis_service.create_email_analysis_workflow",
        lambda **kwargs: DummyGraph({"analysis_id": "a-1", "is_cached_result": True}),
    )

    service = AnalysisService(
        settings=settings,
        session_factory=session_factory,
        analysis_repo=AnalysisRepository(),
        job_repo=JobRepository(),
        report_store=ReportStore(settings.report_output_dir),
    )

    job_id = service.submit_job(b"raw")
    service.process_job(job_id, b"raw")

    job = service.get_job(job_id)
    assert job is not None
    assert job.status == "cached"
    assert job.analysis_id == "a-1"



def test_process_job_marks_failed(monkeypatch, tmp_path):
    settings = _build_settings(tmp_path)
    engine, session_factory = create_engine_and_session(settings.sqlite_db_path)
    init_db(engine)

    class FailingGraph:
        def invoke(self, _state, config=None):
            raise RuntimeError("boom")

    monkeypatch.setattr(
        "backend.services.analysis_service.create_email_analysis_workflow",
        lambda **kwargs: FailingGraph(),
    )

    service = AnalysisService(
        settings=settings,
        session_factory=session_factory,
        analysis_repo=AnalysisRepository(),
        job_repo=JobRepository(),
        report_store=ReportStore(settings.report_output_dir),
    )

    job_id = service.submit_job(b"raw")
    service.process_job(job_id, b"raw")

    job = service.get_job(job_id)
    assert job is not None
    assert job.status == "failed"
    assert "boom" in (job.error or "")


def test_process_job_exposes_stage_progress(monkeypatch, tmp_path):
    settings = _build_settings(tmp_path)
    engine, session_factory = create_engine_and_session(settings.sqlite_db_path)
    init_db(engine)

    monkeypatch.setattr(
        "backend.services.analysis_service.create_email_analysis_workflow",
        lambda **kwargs: StreamingGraph(),
    )

    service = AnalysisService(
        settings=settings,
        session_factory=session_factory,
        analysis_repo=AnalysisRepository(),
        job_repo=JobRepository(),
        report_store=ReportStore(settings.report_output_dir),
    )

    job_id = service.submit_job(b"raw")
    service.process_job(job_id, b"raw")

    progress = service.get_job_progress(job_id)
    assert progress is not None
    assert progress["current_stage"] == "cached"
    assert "fingerprint_email" in progress["completed_stages"]
    assert "check_existing_analysis" in progress["completed_stages"]
    assert progress["total_stages"] == 2
