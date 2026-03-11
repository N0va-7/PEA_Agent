from backend.agent_tools.url_reputation_vt import make_url_reputation_vt_tool
from backend.infra.config import Settings
from backend.workflow.state import EmailAnalysisState


def make_url_reputation_vt_node(settings: Settings, session_factory):
    tool = make_url_reputation_vt_tool(settings, session_factory)

    def url_reputation_vt(state: EmailAnalysisState):
        result = tool.run({"url_extraction": state.get("url_extraction", {}) or {}})
        return {
            "url_reputation": result.get("url_reputation", {}),
            "execution_trace": state["execution_trace"] + ["url_reputation_vt"],
        }

    return url_reputation_vt
