from __future__ import annotations

import email
import re
from email import policy
from email.header import decode_header, make_header
from email.utils import getaddresses
from pathlib import Path
from time import time
from typing import Any

from backend.agent_tools.base import AnalysisTool
from backend.infra.config import Settings


def _decode_str(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return str(value or "")


def _parse_address_header(msg, header_name: str) -> str:
    values = msg.get_all(header_name, [])
    addresses: list[str] = []
    for display_name, addr in getaddresses(values):
        decoded_name = _decode_str(display_name).strip()
        decoded_addr = str(addr or "").strip()
        if decoded_addr:
            addresses.append(decoded_addr)
        elif decoded_name:
            addresses.append(decoded_name)
    if addresses:
        return ", ".join(dict.fromkeys(addresses))
    return _decode_str(msg.get(header_name) or "").strip()


def _collect_bodies(msg) -> tuple[list[str], list[str]]:
    plain_parts: list[str] = []
    html_parts: list[str] = []
    for part in msg.walk():
        if part.get_filename():
            continue
        content_type = part.get_content_type()
        if content_type not in {"text/plain", "text/html"}:
            continue
        charset = part.get_content_charset() or "utf-8"
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        text = payload.decode(charset, errors="ignore").strip()
        if not text:
            continue
        if content_type == "text/html":
            html_parts.append(text)
        else:
            plain_parts.append(text)
    return plain_parts, html_parts


def _cleanup_old_uploads(upload_dir: Path, retention_hours: int, max_delete: int = 100):
    cutoff = time() - max(1, retention_hours) * 3600
    deleted = 0
    for file_path in upload_dir.iterdir():
        if deleted >= max_delete:
            break
        if not file_path.is_file():
            continue
        if file_path.name.startswith(".gitkeep"):
            continue
        try:
            if file_path.stat().st_mtime < cutoff:
                file_path.unlink(missing_ok=True)
                deleted += 1
        except Exception:
            continue


def make_email_parser_tool(settings: Settings) -> AnalysisTool:
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    def runner(context: dict[str, Any]) -> dict[str, Any]:
        _cleanup_old_uploads(upload_dir, settings.upload_retention_hours)
        raw_eml_content = context.get("raw_eml_content") or b""
        analysis_id = str(context.get("analysis_id") or "")
        if not raw_eml_content:
            return {"parsed_email": {}}

        msg = email.message_from_bytes(raw_eml_content, policy=policy.default)
        from_addr = _parse_address_header(msg, "From")
        to_addr = _parse_address_header(msg, "To")
        subject = _decode_str(msg.get("Subject") or "")
        plain_parts, html_parts = _collect_bodies(msg)
        html_body = "\n".join(html_parts).strip()
        plain_body = "\n".join(plain_parts).strip()
        body = plain_body or html_body

        attachments: list[dict[str, Any]] = []
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

            safe_name = f"{analysis_id}_{idx}_{base_name}"
            file_path = upload_dir / safe_name
            with open(file_path, "wb") as handle:
                handle.write(payload)

            attachments.append(
                {
                    "filename": filename,
                    "stored_path": str(file_path),
                    "content_type": part.get_content_type(),
                    "size": len(payload),
                }
            )

        headers = {str(key): _decode_str(value) for key, value in msg.items()}
        parsed_email = {
            "message_id": _decode_str(msg.get("Message-ID") or ""),
            "sender": str(from_addr),
            "recipient": str(to_addr),
            "subject": str(subject),
            "plain_body": str(plain_body),
            "html_body": str(html_body),
            "body": str(body),
            "attachments": attachments,
            "headers": headers,
        }
        return {"parsed_email": parsed_email}

    return AnalysisTool(
        tool_name="email_parser",
        version="1.0.0",
        input_schema={"raw_eml_content": "bytes", "analysis_id": "str"},
        output_schema={"parsed_email": "dict"},
        runner=runner,
    )
