from pathlib import Path

from backend.agent_tools.content_review import make_content_review_tool
from backend.workflow.state import EmailAnalysisState


def make_llm_content_review_node(llm, _model_dir: Path):
    tool = make_content_review_tool(llm)

    def content_review(state: EmailAnalysisState):
        result = tool.run(
            {
                "parsed_email": state.get("parsed_email", {}) or {},
                "url_analysis": state.get("url_analysis", {}) or {},
                "url_reputation": state.get("url_reputation", {}) or {},
                "attachment_analysis": state.get("attachment_analysis", {}) or {},
            }
        )
        return {
            "content_review": result.get("content_review", {}),
            "execution_trace": state["execution_trace"] + ["content_review"],
        }

    return content_review
