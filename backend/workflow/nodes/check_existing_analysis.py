from datetime import datetime, timezone

from backend.repositories.analysis_repo import AnalysisRepository
from backend.workflow.state import EmailAnalysisState



def make_check_existing_analysis_node(analysis_repo: AnalysisRepository, session_factory):
    def check_existing_analysis(state: EmailAnalysisState):
        with session_factory() as db:
            existing = analysis_repo.get_existing(
                db,
                message_id=state.get("message_id") or None,
                fingerprint=state["email_fingerprint"],
            )

        if not existing:
            return {
                "is_cached_result": False,
                "execution_trace": state["execution_trace"] + ["check_existing_analysis_miss"],
            }

        return {
            "analysis_id": existing.id,
            "is_cached_result": True,
            "message_id": existing.message_id or state.get("message_id") or "",
            "parsed_email": existing.parsed_email or {},
            "url_extraction": existing.url_extraction or {},
            "url_reputation": existing.url_reputation or {},
            "url_analysis": existing.url_analysis or {},
            "content_review": existing.content_review or {},
            "attachment_analysis": existing.attachment_analysis or {},
            "decision": existing.decision or {},
            "report": {
                "markdown": existing.report_markdown or "",
                "summary": "",
                "path": existing.report_path,
            },
            "report_path": existing.report_path,
            "created_at": existing.created_at.isoformat() if existing.created_at else datetime.now(timezone.utc).isoformat(),
            "execution_trace": state["execution_trace"] + ["check_existing_analysis_hit"],
        }

    return check_existing_analysis
