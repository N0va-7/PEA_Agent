from pathlib import Path

from backend.agent_tools.url_model_analysis import make_url_model_analysis_tool
from backend.workflow.state import EmailAnalysisState


def make_url_reputation_node(model_dir: Path):
    tool = make_url_model_analysis_tool(model_dir)

    def url_model_analysis(state: EmailAnalysisState):
        result = tool.run(
            {
                "url_extraction": state.get("url_extraction", {}) or {},
                "url_reputation": state.get("url_reputation", {}) or {},
            }
        )
        return {
            "url_analysis": result.get("url_analysis", {}),
            "execution_trace": state["execution_trace"] + ["url_model_analysis"],
        }

    return url_model_analysis
