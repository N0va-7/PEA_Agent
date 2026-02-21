from langgraph.graph import END, START, StateGraph

from backend.infra.config import Settings
from backend.repositories.analysis_repo import AnalysisRepository
from backend.workflow.edges import (
    route_after_attachment_analysis,
    route_after_body_analysis,
    route_after_check_existing,
    route_after_parse_eml,
    route_after_url_analysis,
)
from backend.workflow.llm import build_llm
from backend.workflow.nodes.analysis import make_analysis_node
from backend.workflow.nodes.attachment_reputation import make_attachment_reputation_node
from backend.workflow.nodes.body_reputation import make_body_reputation_node
from backend.workflow.nodes.check_existing_analysis import make_check_existing_analysis_node
from backend.workflow.nodes.extract_urls import make_extract_urls_node
from backend.workflow.nodes.fingerprint_email import make_fingerprint_email_node
from backend.workflow.nodes.llm_report import make_llm_report_node
from backend.workflow.nodes.parse_eml import make_parse_eml_node
from backend.workflow.nodes.persist_analysis import make_persist_analysis_node
from backend.workflow.nodes.url_reputation import make_url_reputation_node
from backend.workflow.state import EmailAnalysisState



def create_email_analysis_workflow(
    settings: Settings,
    analysis_repo: AnalysisRepository,
    session_factory,
    report_store,
):
    llm = build_llm(settings)

    workflow = StateGraph(EmailAnalysisState)

    workflow.add_node("fingerprint_email", make_fingerprint_email_node())
    workflow.add_node("check_existing_analysis", make_check_existing_analysis_node(analysis_repo, session_factory))
    workflow.add_node("parse_eml_file", make_parse_eml_node(settings))
    workflow.add_node("extract_urls", make_extract_urls_node(llm))
    workflow.add_node("analyze_attachment_reputation", make_attachment_reputation_node(settings.threatbook_api_key))
    workflow.add_node("analyze_body_reputation", make_body_reputation_node(settings.model_dir))
    workflow.add_node("analyze_url_reputation", make_url_reputation_node(settings.model_dir))
    workflow.add_node("analyze_email_data", make_analysis_node(settings.model_dir))
    workflow.add_node("llm_report", make_llm_report_node(llm))
    workflow.add_node("persist_analysis", make_persist_analysis_node(analysis_repo, session_factory, report_store))

    workflow.add_edge(START, "fingerprint_email")
    workflow.add_edge("fingerprint_email", "check_existing_analysis")
    workflow.add_conditional_edges(
        "check_existing_analysis",
        route_after_check_existing,
        {
            "END": END,
            "parse_eml_file": "parse_eml_file",
        },
    )
    workflow.add_edge("parse_eml_file", "extract_urls")

    workflow.add_conditional_edges(
        "extract_urls",
        route_after_parse_eml,
        {
            "analyze_attachment_reputation": "analyze_attachment_reputation",
            "analyze_body_reputation": "analyze_body_reputation",
            "analyze_email_data": "analyze_email_data",
        },
    )
    workflow.add_conditional_edges(
        "analyze_attachment_reputation",
        route_after_attachment_analysis,
        {
            "analyze_body_reputation": "analyze_body_reputation",
            "analyze_email_data": "analyze_email_data",
        },
    )
    workflow.add_conditional_edges(
        "analyze_body_reputation",
        route_after_body_analysis,
        {
            "analyze_url_reputation": "analyze_url_reputation",
            "analyze_email_data": "analyze_email_data",
        },
    )
    workflow.add_conditional_edges(
        "analyze_url_reputation",
        route_after_url_analysis,
        {
            "analyze_email_data": "analyze_email_data",
        },
    )

    workflow.add_edge("analyze_email_data", "llm_report")
    workflow.add_edge("llm_report", "persist_analysis")
    workflow.add_edge("persist_analysis", END)

    return workflow.compile()
