from backend.workflow.state import EmailAnalysisState



def route_after_check_existing(state: EmailAnalysisState) -> str:
    if state.get("is_cached_result"):
        return "END"
    return "parse_eml_file"



def route_after_parse_eml(state: EmailAnalysisState) -> str:
    if state["attachments"]:
        return "analyze_attachment_reputation"
    if state["body"]:
        return "analyze_body_reputation"
    return "analyze_email_data"



def route_after_attachment_analysis(state: EmailAnalysisState) -> str:
    if state["attachment_analysis"]["threat_level"] == "bad":
        return "analyze_email_data"
    if state["body"]:
        return "analyze_body_reputation"
    return "analyze_email_data"



def route_after_body_analysis(state: EmailAnalysisState) -> str:
    if state["urls"]:
        return "analyze_url_reputation"
    return "analyze_email_data"



def route_after_url_analysis(state: EmailAnalysisState) -> str:
    return "analyze_email_data"
