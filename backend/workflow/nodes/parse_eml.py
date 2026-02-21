import email
import re
from pathlib import Path
from email.header import decode_header
from email.utils import parseaddr

from backend.infra.config import Settings
from backend.workflow.state import EmailAnalysisState



def _decode_str(s):
    if not s:
        return ""
    try:
        value, charset = decode_header(s)[0]
        if isinstance(value, bytes):
            return value.decode(charset or "utf-8", errors="ignore")
        if isinstance(value, str):
            return value
    except Exception:
        return s
    return s



def _get_body(msg):
    if msg.is_multipart():
        for part in msg.get_payload():
            body = _get_body(part)
            if body:
                return body.strip()
    else:
        content_type = msg.get_content_type()
        if content_type in ["text/plain", "text/html"]:
            charset = msg.get_content_charset() or "utf-8"
            payload = msg.get_payload(decode=True)
            if payload:
                return payload.decode(charset, errors="ignore").strip()
    return ""



def make_parse_eml_node(settings: Settings):
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    def parse_eml_file(state: EmailAnalysisState):
        if not state.get("raw_eml_content"):
            return {
                "execution_trace": state["execution_trace"] + ["parse_eml_error"],
            }

        msg = email.message_from_bytes(state["raw_eml_content"])

        from_addr = _decode_str(parseaddr(msg.get("From") or "")[1])
        to_addr = _decode_str(parseaddr(msg.get("To") or "")[1])
        subject = _decode_str(msg.get("Subject") or "")
        body = _get_body(msg)

        attachments = []
        for idx, part in enumerate(msg.walk()):
            filename = part.get_filename()
            if not filename:
                continue
            filename = _decode_str(filename)
            payload = part.get_payload(decode=True)
            if not payload:
                continue

            base_name = Path(filename).name
            base_name = re.sub(r"[^A-Za-z0-9._-]", "_", base_name)
            if not base_name:
                base_name = f"attachment_{idx}.bin"

            safe_name = f"{state['analysis_id']}_{idx}_{base_name}"
            file_path = upload_dir / safe_name
            with open(file_path, "wb") as f:
                f.write(payload)

            attachments.append(
                {
                    "filename": filename,
                    "stored_path": str(file_path),
                    "content_type": part.get_content_type(),
                    "size": len(payload),
                }
            )

        return {
            "sender": str(from_addr),
            "recipient": str(to_addr),
            "subject": str(subject),
            "body": str(body),
            "attachments": attachments,
            "execution_trace": state["execution_trace"] + ["parse_eml_file"],
        }

    return parse_eml_file
