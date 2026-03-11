from backend.agent_tools.email_parser import make_email_parser_tool
from backend.infra.config import Settings
from backend.workflow.state import EmailAnalysisState


def make_parse_eml_node(settings: Settings):
    tool = make_email_parser_tool(settings)

    def email_parser(state: EmailAnalysisState):
        parsed_email = tool.run(
            {
                "raw_eml_content": state.get("raw_eml_content"),
                "analysis_id": state.get("analysis_id"),
            }
        ).get("parsed_email", {})
        return {
            "message_id": str(parsed_email.get("message_id") or state.get("message_id") or ""),
            "parsed_email": parsed_email,
            "execution_trace": state["execution_trace"] + ["email_parser"],
        }

    return email_parser
