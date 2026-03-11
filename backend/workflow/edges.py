from backend.workflow.state import EmailAnalysisState


def route_after_check_existing(state: EmailAnalysisState) -> str:
    if state.get("is_cached_result"):
        return "END"
    return "email_parser"
