from typing import Any, Dict, List, Optional, TypedDict


class EmailAnalysisState(TypedDict):
    raw_eml_content: Optional[bytes]

    message_id: str
    email_fingerprint: str
    analysis_id: str
    is_cached_result: bool
    report_path: str
    created_at: str

    sender: str
    recipient: str
    subject: str
    body: str
    urls: List[str]
    attachments: List[Dict[str, Any]]

    url_analysis: Optional[Dict[str, Any]]
    body_analysis: Optional[Dict[str, Any]]
    attachment_analysis: Optional[Dict[str, Any]]

    final_decision: Optional[Dict[str, Any]]
    llm_report: Optional[str]

    execution_trace: List[str]
