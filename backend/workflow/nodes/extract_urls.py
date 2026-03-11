from backend.agent_tools.url_extractor import make_url_extractor_tool
from backend.workflow.state import EmailAnalysisState


def make_extract_urls_node(_llm=None):
    tool = make_url_extractor_tool()

    def url_extractor(state: EmailAnalysisState):
        result = tool.run({"parsed_email": state.get("parsed_email", {}) or {}})
        extraction = result.get("url_extraction", {})
        return {
            "url_extraction": extraction,
            "execution_trace": state["execution_trace"] + ["url_extractor"],
        }

    return url_extractor
