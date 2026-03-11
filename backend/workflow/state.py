from typing import Any, Dict, List, Optional, TypedDict


class EmailAnalysisState(TypedDict):
    raw_eml_content: Optional[bytes]

    message_id: str
    email_fingerprint: str
    analysis_id: str
    is_cached_result: bool
    report_path: str
    created_at: str

    parsed_email: Optional[Dict[str, Any]]
    url_extraction: Optional[Dict[str, Any]]
    url_reputation: Optional[Dict[str, Any]]
    url_analysis: Optional[Dict[str, Any]]
    content_review: Optional[Dict[str, Any]]
    attachment_analysis: Optional[Dict[str, Any]]
    decision: Optional[Dict[str, Any]]
    report: Optional[Dict[str, Any]]

    execution_trace: List[str]
