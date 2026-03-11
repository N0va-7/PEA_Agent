from backend.agent_tools.decision_engine import make_decision_engine_tool
from backend.workflow.state import EmailAnalysisState


def make_decision_engine_v2_node():
    tool = make_decision_engine_tool()

    def decision_engine(state: EmailAnalysisState):
        result = tool.run(
            {
                "url_reputation": state.get("url_reputation", {}) or {},
                "url_analysis": state.get("url_analysis", {}) or {},
                "content_review": state.get("content_review", {}) or {},
                "attachment_analysis": state.get("attachment_analysis", {}) or {},
            }
        )
        return {
            "decision": result.get("decision", {}),
            "execution_trace": state["execution_trace"] + ["decision_engine"],
        }

    return decision_engine
