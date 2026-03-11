from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import SystemMessage

from backend.agent_tools.base import AnalysisTool


def _has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def _safe_list(value: Any, *, limit: int = 8) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    for item in value[:limit]:
        text = str(item or "").strip()
        if text:
            cleaned.append(text)
    return cleaned


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def _extract_json_payload(content: str) -> dict[str, Any]:
    raw = (content or "").strip()
    if not raw:
        return {}
    for pattern in [r"<json>\s*(\{.*?\})\s*</json>", r"```json\s*(\{.*?\})\s*```"]:
        match = re.search(pattern, raw, re.DOTALL | re.IGNORECASE)
        if match:
            try:
                payload = json.loads(match.group(1).strip())
                return payload if isinstance(payload, dict) else {}
            except json.JSONDecodeError:
                pass
    first = raw.find("{")
    last = raw.rfind("}")
    if first >= 0 and last > first:
        try:
            payload = json.loads(raw[first : last + 1].strip())
            return payload if isinstance(payload, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _derive_summary(context: dict[str, Any], enrich: dict[str, Any]) -> str:
    decision = context.get("decision", {}) or {}
    content_review = context.get("content_review", {}) or {}
    summary = str(enrich.get("summary") or "").strip()
    if summary and _has_cjk(summary):
        return summary

    verdict = str(decision.get("verdict") or "unknown")
    verdict_label = {"malicious": "恶意", "suspicious": "可疑", "benign": "正常"}.get(verdict, verdict or "未判定")
    primary = str(decision.get("primary_risk_source") or "none").strip()
    reasons = _safe_list(decision.get("reasons"), limit=2) or _safe_list(content_review.get("reasons"), limit=2)

    base = f"最终判定为{verdict_label}"
    if primary and primary != "none":
        base += f"，主风险源为 {primary}"
    if reasons:
        return f"{base}。关键依据：{'；'.join(reasons)}。"
    return f"{base}。"


def _derive_key_indicators(context: dict[str, Any], enrich: dict[str, Any]) -> list[str]:
    provided = _safe_list(enrich.get("key_indicators"))
    if provided:
        return provided

    decision = context.get("decision", {}) or {}
    url_reputation = context.get("url_reputation", {}) or {}
    url_analysis = context.get("url_analysis", {}) or {}
    content_review = context.get("content_review", {}) or {}
    attachment_analysis = context.get("attachment_analysis", {}) or {}

    indicators: list[str] = []
    indicators.extend(_safe_list(decision.get("reasons"), limit=3))
    indicators.extend(_safe_list(content_review.get("evidence"), limit=3))

    high_risk_urls = [str(item).strip() for item in (url_reputation.get("high_risk_urls") or []) if str(item).strip()]
    if high_risk_urls:
        indicators.append(f"VT 高危 URL：{high_risk_urls[0]}")

    max_url_score = url_analysis.get("max_possibility")
    if max_url_score not in (None, ""):
        try:
            indicators.append(f"URL 模型最高风险分 {float(max_url_score):.4f}")
        except (TypeError, ValueError):
            pass

    attachment_summary = str(attachment_analysis.get("summary") or "").strip()
    if attachment_summary and attachment_summary != "邮件无附件":
        indicators.append(attachment_summary)

    return _dedupe_keep_order(indicators)[:6]


def _derive_recommendations(context: dict[str, Any], enrich: dict[str, Any]) -> list[str]:
    provided = _safe_list(enrich.get("recommendations"))
    if provided:
        return provided

    decision = context.get("decision", {}) or {}
    content_review = context.get("content_review", {}) or {}
    attachment_analysis = context.get("attachment_analysis", {}) or {}

    recommendations: list[str] = []
    recommendations.append(str(decision.get("recommended_action") or "").strip())
    recommendations.append(str(content_review.get("recommended_action") or "").strip())

    attachment_verdict = str(attachment_analysis.get("aggregate_verdict") or "").strip().lower()
    attachment_summary = str(attachment_analysis.get("summary") or "").strip()
    if attachment_verdict in {"malicious", "suspicious"} and attachment_summary:
        recommendations.append(attachment_summary)

    return _dedupe_keep_order(recommendations)[:5]


def _build_markdown(context: dict[str, Any], enrich: dict[str, Any]) -> str:
    parsed_email = context.get("parsed_email", {}) or {}
    url_reputation = context.get("url_reputation", {}) or {}
    url_analysis = context.get("url_analysis", {}) or {}
    content_review = context.get("content_review", {}) or {}
    attachment_analysis = context.get("attachment_analysis", {}) or {}
    decision = context.get("decision", {}) or {}

    verdict = str(decision.get("verdict") or "unknown")
    verdict_label = {"malicious": "恶意", "suspicious": "可疑", "benign": "正常"}.get(verdict, verdict or "未判定")
    risk_level = "高" if verdict == "malicious" else "中" if verdict == "suspicious" else "低"
    summary = _derive_summary(context, enrich)
    key_indicators = _derive_key_indicators(context, enrich)
    recommendations = _derive_recommendations(context, enrich)
    indicators_md = "\n".join(f"- {item}" for item in key_indicators)
    rec_md = "\n".join(f"{idx}. {item}" for idx, item in enumerate(recommendations, start=1))
    snapshot = json.dumps(
        {
            "decision": decision,
            "content_review": content_review,
            "url_reputation": url_reputation,
            "url_analysis": url_analysis,
            "attachment_analysis": attachment_analysis,
        },
        ensure_ascii=False,
        indent=2,
    )
    return (
        "# 邮件威胁分析报告\n\n"
        "## 1. 执行摘要\n"
        f"{summary}\n\n"
        "## 2. 邮件基础信息\n"
        f"- 主题: {parsed_email.get('subject') or '--'}\n"
        f"- 发件人: {parsed_email.get('sender') or '--'}\n"
        f"- 收件人: {parsed_email.get('recipient') or '--'}\n\n"
        "## 3. 检测结果总览\n"
        f"- 最终判定: {verdict_label}\n"
        f"- 风险等级: {risk_level}\n"
        f"- 主要风险源: {decision.get('primary_risk_source') or '--'}\n\n"
        "## 4. 关键证据\n"
        f"{indicators_md}\n\n"
        "## 5. 处置建议\n"
        f"{rec_md}\n\n"
        "## 6. 模型输出快照\n"
        "```json\n"
        f"{snapshot}\n"
        "```\n"
    )


def make_report_renderer_tool(llm) -> AnalysisTool:
    def runner(context: dict[str, Any]) -> dict[str, Any]:
        enrich: dict[str, Any] = {}
        if llm is not None:
            prompt = f"""
你是邮件安全报告整理工具。你只能输出 JSON。
字段：
- summary: 简体中文摘要
- key_indicators: 4 到 6 条中文证据
- recommendations: 3 到 5 条中文处置建议

输入：
{json.dumps({
    "parsed_email": context.get("parsed_email", {}),
    "decision": context.get("decision", {}),
    "url_reputation": context.get("url_reputation", {}),
    "url_analysis": context.get("url_analysis", {}),
    "content_review": context.get("content_review", {}),
    "attachment_analysis": context.get("attachment_analysis", {}),
}, ensure_ascii=False)}
"""
            try:
                response = llm.invoke([SystemMessage(content=prompt)])
                enrich = _extract_json_payload(str(getattr(response, "content", "") or ""))
            except Exception:
                enrich = {}
        markdown = _build_markdown(context, enrich)
        return {
            "report": {
                "markdown": markdown,
                "summary": str((enrich or {}).get("summary") or "").strip(),
                "path": "",
            }
        }

    return AnalysisTool(
        tool_name="report_renderer",
        version="1.0.0",
        input_schema={"parsed_email": "dict", "decision": "dict"},
        output_schema={"report": "dict"},
        runner=runner,
    )
