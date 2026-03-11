from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import requests

from backend.agent_tools.base import AnalysisTool
from backend.infra.config import Settings


def _default_item(filename: str, summary: str = "unknown") -> dict[str, Any]:
    return {
        "filename": filename,
        "verdict": "unknown",
        "score": 0.0,
        "summary": summary,
        "artifacts": [],
    }


def make_attachment_sandbox_tool(settings: Settings) -> AnalysisTool:
    def runner(context: dict[str, Any]) -> dict[str, Any]:
        parsed_email = context.get("parsed_email", {}) or {}
        attachments = parsed_email.get("attachments", []) or []

        if not attachments:
            return {
                "attachment_analysis": {
                    "aggregate_verdict": "no_attachment",
                    "score": 0.0,
                    "items": [],
                    "summary": "邮件无附件",
                    "source": "attachment_sandbox",
                }
            }

        if not settings.attachment_sandbox_base_url:
            items = [_default_item(str(item.get("filename") or "attachment.bin"), "sandbox_disabled") for item in attachments]
            return {
                "attachment_analysis": {
                    "aggregate_verdict": "unknown",
                    "score": 0.0,
                    "items": items,
                    "summary": "附件沙箱未启用，已降级继续",
                    "source": "attachment_sandbox",
                }
            }

        items: list[dict[str, Any]] = []
        aggregate_verdict = "benign"
        max_score = 0.0

        base_url = settings.attachment_sandbox_base_url.rstrip("/")
        for attachment in attachments:
            filename = str(attachment.get("filename") or "attachment.bin")
            stored_path = Path(str(attachment.get("stored_path") or ""))
            if not stored_path.exists():
                items.append(_default_item(filename, "missing_attachment_payload"))
                aggregate_verdict = "unknown"
                continue
            try:
                with open(stored_path, "rb") as handle:
                    response = requests.post(
                        f"{base_url}/analysis/jobs",
                        files={"file": (filename, handle)},
                        data={"source_id": settings.attachment_sandbox_source_id},
                        timeout=max(5, settings.attachment_sandbox_timeout_seconds),
                    )
                response.raise_for_status()
                job_id = str((response.json() or {}).get("job_id") or "")
                if not job_id:
                    raise RuntimeError("missing job_id")
                deadline = time.monotonic() + max(5, settings.attachment_sandbox_timeout_seconds)
                payload = None
                while time.monotonic() < deadline:
                    poll = requests.get(
                        f"{base_url}/analysis/jobs/{job_id}",
                        timeout=max(5, settings.attachment_sandbox_timeout_seconds),
                    )
                    poll.raise_for_status()
                    payload = poll.json()
                    if str(payload.get("status") or "").lower() in {"done", "succeeded", "completed"}:
                        break
                    if str(payload.get("status") or "").lower() == "error":
                        break
                    time.sleep(max(1, settings.attachment_sandbox_poll_interval_seconds))

                payload = payload or {}
                verdict = str(payload.get("verdict") or "unknown").lower()
                risk_score = float(payload.get("risk_score") or 0)
                item_verdict = "benign"
                if verdict == "block":
                    item_verdict = "malicious"
                elif verdict == "quarantine":
                    item_verdict = "suspicious"
                elif verdict == "allow":
                    item_verdict = "benign"
                else:
                    item_verdict = "unknown"
                items.append(
                    {
                        "filename": filename,
                        "verdict": item_verdict,
                        "score": round(min(1.0, max(0.0, risk_score / 100.0)), 6),
                        "summary": " / ".join(str(reason) for reason in (payload.get("reasons") or []) if str(reason)),
                        "artifacts": payload.get("artifacts") or [],
                    }
                )
            except Exception:
                items.append(_default_item(filename, "sandbox_error"))

        for item in items:
            max_score = max(max_score, float(item.get("score") or 0.0))
            verdict = str(item.get("verdict") or "unknown")
            if verdict == "malicious":
                aggregate_verdict = "malicious"
                break
            if verdict == "suspicious":
                aggregate_verdict = "suspicious"
            elif verdict == "unknown" and aggregate_verdict == "benign":
                aggregate_verdict = "unknown"

        return {
            "attachment_analysis": {
                "aggregate_verdict": aggregate_verdict,
                "score": round(max_score, 6),
                "items": items,
                "summary": "附件沙箱已完成分析" if items else "邮件无附件",
                "source": "attachment_sandbox",
            }
        }

    return AnalysisTool(
        tool_name="attachment_sandbox",
        version="1.0.0",
        input_schema={"parsed_email": "dict"},
        output_schema={"attachment_analysis": "dict"},
        runner=runner,
    )
