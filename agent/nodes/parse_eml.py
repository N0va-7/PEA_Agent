import email
import re
from models.ollama_llm import llm
from email.header import decode_header
from email.utils import parseaddr
from state.state import EmailAnalysisState


def decode_str(s):
    if not s:
        return ""
    try:
        value, charset = decode_header(s)[0]
        if isinstance(value, bytes):
            if charset:
                return value.decode(charset)
            else:
                return value.decode('utf-8', errors='ignore')
        elif isinstance(value, str):
            return value
    except:
        return s
    return s

def get_body(msg):
    if msg.is_multipart():
        for part in msg.get_payload():
            body = get_body(part)
            if body:
                return body.strip()
    else:
        content_type = msg.get_content_type()
        if content_type in ["text/plain", "text/html"]:
            charset = msg.get_content_charset() or "utf-8"
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    return payload.decode(charset, errors="ignore").strip()
            except:
                pass
    return ""


def parse_eml_file(state: EmailAnalysisState):
    """
    Node 1: 解析 EML 文件
    """
    if not state["raw_eml_content"]:
        return {
            "execution_trace": state["execution_trace"] + ["parse_eml_error"]
        }

    msg = email.message_from_bytes(state["raw_eml_content"])

    # 提取基本信息
    from_addr = parseaddr(msg.get("From") or "")[1]
    to_addr = parseaddr(msg.get("To") or "")[1]
    subject = msg.get("Subject") or ""

    from_addr = decode_str(from_addr)
    to_addr = decode_str(to_addr)
    subject = decode_str(subject)
    body = get_body(msg)

    # 提取 URL
    # urls = extract_urls(state)

    # 提取附件
    print("检查是否存在附件")
    attachments = []
    for part in msg.walk():
        filename = part.get_filename()
        if filename:
            filename = decode_str(filename)
            content_type = part.get_content_type()
            payload = part.get_payload(decode=True)
            size = len(payload) if payload else 0
            attachments.append({
                "filename": filename,
                "content_type": content_type,
                # "size": size,
                # "payload": payload  # 用于后续沙箱分析
            })
            with open(f'./uploads/{filename}', 'wb') as f:
                f.write(payload)
            print(f"发现附件: {filename}")
    print("附件数量:", len(attachments))
    print(attachments)
    return {
        "sender": str(from_addr),
        "recipient": str(to_addr),
        "subject": str(subject),
        "body": str(body),
        # "urls": urls,
        "attachments": attachments,
        "execution_trace": ["parse_eml"]
    }
