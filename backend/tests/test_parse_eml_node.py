from email.header import Header

from backend.infra.config import Settings
from backend.workflow.nodes.parse_eml import make_parse_eml_node


def _settings(tmp_path):
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'analysis.db'}",
        sqlite_db_path=tmp_path / "analysis.db",
        report_output_dir=tmp_path / "reports",
        upload_dir=tmp_path / "uploads",
        model_dir=tmp_path,
        llm_api_key="",
        llm_base_url="https://api.openai.com/v1",
        llm_model_id="gpt-4o-mini",
        vt_api_key="",
        vt_base_url="https://www.virustotal.com/api/v3",
        vt_enabled=True,
        vt_public_mode=True,
        vt_cache_ttl_hours=24,
        vt_min_interval_seconds=15,
        vt_daily_budget=500,
        vt_timeout_seconds=20,
        attachment_sandbox_base_url="",
        attachment_sandbox_source_id="pea-agent",
        attachment_sandbox_timeout_seconds=45,
        attachment_sandbox_poll_interval_seconds=2,
        jwt_secret_key="secret",
        jwt_algorithm="HS256",
        jwt_expire_hours=8,
        cors_allow_origins=["http://localhost:5173"],
        auth_username="admin",
        auth_password_hash="x",
        job_queue_backend="memory",
        redis_url="",
        redis_queue_name="pea:jobs",
        upload_retention_hours=72,
        login_rate_max_attempts=10,
        login_rate_window_seconds=300,
        expose_internal_error_details=False,
    )


def test_parse_eml_node_parses_sender_recipient_and_decoded_subject(tmp_path):
    subject = Header("账户安全校验通知", "utf-8").encode()
    raw = (
        f"From: 安全中心 <alerts@example.com>\n"
        f"To: 张三 <user@example.com>, ops@example.com\n"
        f"Subject: {subject}\n"
        f"MIME-Version: 1.0\n"
        f"Content-Type: text/plain; charset=utf-8\n\n"
        f"请尽快核验账号状态。\n"
    ).encode("utf-8")

    node = make_parse_eml_node(_settings(tmp_path))
    out = node({"analysis_id": "a-1", "raw_eml_content": raw, "execution_trace": []})
    parsed_email = out["parsed_email"]

    assert parsed_email["sender"] == "alerts@example.com"
    assert parsed_email["recipient"] == "user@example.com, ops@example.com"
    assert parsed_email["subject"] == "账户安全校验通知"
    assert "请尽快核验账号状态" in parsed_email["plain_body"]
    assert out["execution_trace"][-1] == "email_parser"
