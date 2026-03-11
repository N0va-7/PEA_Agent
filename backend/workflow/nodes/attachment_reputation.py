from backend.agent_tools.attachment_sandbox import make_attachment_sandbox_tool
from backend.infra.config import Settings
from backend.workflow.state import EmailAnalysisState


def make_attachment_reputation_node(settings: Settings):
    tool = make_attachment_sandbox_tool(settings)

    def attachment_sandbox(state: EmailAnalysisState):
        result = tool.run({"parsed_email": state.get("parsed_email", {}) or {}})
        return {
            "attachment_analysis": result.get("attachment_analysis", {}),
            "execution_trace": state["execution_trace"] + ["attachment_sandbox"],
        }

    return attachment_sandbox
