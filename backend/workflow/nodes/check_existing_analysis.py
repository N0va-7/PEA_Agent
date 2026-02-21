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
            "sender": existing.sender or "",
            "recipient": existing.recipient or "",
            "subject": existing.subject or "",
            "body": state.get("body", ""),
            "urls": state.get("urls", []),
            "attachments": state.get("attachments", []),
            "url_analysis": existing.url_analysis or {},
            "body_analysis": existing.body_analysis or {},
            "attachment_analysis": existing.attachment_analysis or {},
            "final_decision": existing.final_decision or {},
            "llm_report": existing.llm_report or "",
            "report_path": existing.report_path,
            "created_at": existing.created_at.isoformat() if existing.created_at else datetime.now(timezone.utc).isoformat(),
            "execution_trace": state["execution_trace"] + ["check_existing_analysis_hit"],
        }

    return check_existing_analysis
