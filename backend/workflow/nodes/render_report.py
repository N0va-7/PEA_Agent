from backend.agent_tools.report_renderer import make_report_renderer_tool
from backend.workflow.state import EmailAnalysisState


def make_render_report_node(llm):
    tool = make_report_renderer_tool(llm)

    def report_renderer(state: EmailAnalysisState):
        result = tool.run(
            {
                "parsed_email": state.get("parsed_email", {}) or {},
                "url_reputation": state.get("url_reputation", {}) or {},
                "url_analysis": state.get("url_analysis", {}) or {},
                "content_review": state.get("content_review", {}) or {},
                "attachment_analysis": state.get("attachment_analysis", {}) or {},
                "decision": state.get("decision", {}) or {},
            }
        )
        return {
            "report": result.get("report", {}),
            "execution_trace": state["execution_trace"] + ["report_renderer"],
        }

    return report_renderer
