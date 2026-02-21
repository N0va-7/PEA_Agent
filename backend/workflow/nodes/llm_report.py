import re

from langchain_core.messages import SystemMessage

from backend.workflow.state import EmailAnalysisState



def make_llm_report_node(llm):
    def llm_report(state: EmailAnalysisState):
        prompt = f"""
You are a senior cybersecurity analyst specializing in phishing and malware detection.
Generate a standardized email threat analysis report in Chinese.
Input data:
- Email Subject: {state.get('subject', '')}
- Sender: {state.get('sender', '')}
- Recipient: {state.get('recipient', '')}
- URL Analysis: {state.get('url_analysis', {})}
- Body Analysis: {state.get('body_analysis', {})}
- Attachment Analysis: {state.get('attachment_analysis', {})}
- Final Decision: {state.get('final_decision', {})}
Output only between <report> and </report> in markdown.
"""
        report = ""
        try:
            response = llm.invoke([SystemMessage(content=prompt)])
            content = (response.content or "").strip()
            match = re.search(r"<report>\s*(.*?)\s*</report>", content, re.DOTALL)
            if match:
                report = match.group(1).strip()
            elif content:
                # If model omits tags, accept raw markdown content.
                report = content
        except Exception as exc:
            raise RuntimeError("LLM report generation failed.") from exc

        if not report:
            raise RuntimeError("LLM report output was empty.")

        return {
            "llm_report": report,
            "execution_trace": state["execution_trace"] + ["llm_report"],
        }

    return llm_report
