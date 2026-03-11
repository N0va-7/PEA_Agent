from langgraph.graph import END, START, StateGraph

from backend.infra.config import Settings
from backend.repositories.analysis_repo import AnalysisRepository
from backend.workflow.edges import route_after_check_existing
from backend.workflow.llm import build_llm
from backend.workflow.nodes.attachment_reputation import make_attachment_reputation_node
from backend.workflow.nodes.check_existing_analysis import make_check_existing_analysis_node
from backend.workflow.nodes.decision_engine_v2 import make_decision_engine_v2_node
from backend.workflow.nodes.extract_urls import make_extract_urls_node
from backend.workflow.nodes.fingerprint_email import make_fingerprint_email_node
from backend.workflow.nodes.llm_content_review import make_llm_content_review_node
from backend.workflow.nodes.parse_eml import make_parse_eml_node
from backend.workflow.nodes.persist_analysis import make_persist_analysis_node
from backend.workflow.nodes.render_report import make_render_report_node
from backend.workflow.nodes.url_reputation import make_url_reputation_node
from backend.workflow.nodes.url_reputation_vt import make_url_reputation_vt_node
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
    workflow.add_node("email_parser", make_parse_eml_node(settings))
    workflow.add_node("url_extractor", make_extract_urls_node())
    workflow.add_node("url_reputation_vt", make_url_reputation_vt_node(settings, session_factory))
    workflow.add_node("url_model_analysis", make_url_reputation_node(settings.model_dir))
    workflow.add_node("attachment_sandbox", make_attachment_reputation_node(settings))
    workflow.add_node("content_review", make_llm_content_review_node(llm, settings.model_dir))
    workflow.add_node("decision_engine", make_decision_engine_v2_node())
    workflow.add_node("report_renderer", make_render_report_node(llm))
    workflow.add_node("persist_analysis", make_persist_analysis_node(analysis_repo, session_factory, report_store))

    workflow.add_edge(START, "fingerprint_email")
    workflow.add_edge("fingerprint_email", "check_existing_analysis")
    workflow.add_conditional_edges(
        "check_existing_analysis",
        route_after_check_existing,
        {
            "END": END,
            "email_parser": "email_parser",
        },
    )
    workflow.add_edge("email_parser", "url_extractor")
    workflow.add_edge("url_extractor", "url_reputation_vt")
    workflow.add_edge("url_reputation_vt", "url_model_analysis")
    workflow.add_edge("url_model_analysis", "attachment_sandbox")
    workflow.add_edge("attachment_sandbox", "content_review")
    workflow.add_edge("content_review", "decision_engine")
    workflow.add_edge("decision_engine", "report_renderer")
    workflow.add_edge("report_renderer", "persist_analysis")
    workflow.add_edge("persist_analysis", END)

    return workflow.compile()
