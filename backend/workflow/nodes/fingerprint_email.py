import email
import hashlib
import uuid

from backend.workflow.state import EmailAnalysisState



def make_fingerprint_email_node():
    def fingerprint_email(state: EmailAnalysisState):
        raw = state.get("raw_eml_content") or b""
        message_id = ""
        if raw:
            try:
                msg = email.message_from_bytes(raw)
                message_id = (msg.get("Message-ID") or "").strip()
            except Exception:
                message_id = ""

        fingerprint = hashlib.sha256(raw).hexdigest()
        analysis_id = str(uuid.uuid4())

        return {
            "message_id": message_id,
            "email_fingerprint": fingerprint,
            "analysis_id": analysis_id,
            "is_cached_result": False,
            "execution_trace": state.get("execution_trace", []) + ["fingerprint_email"],
        }

    return fingerprint_email
