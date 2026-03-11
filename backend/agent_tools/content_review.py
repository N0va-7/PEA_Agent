from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import SystemMessage

from backend.agent_tools.base import AnalysisTool


def _clip01(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed != parsed:
        return default
    return min(1.0, max(0.0, parsed))


def _safe_list(value: Any, *, limit: int = 8) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if not text:
            continue
        cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


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


def _normalize_verdict(value: str) -> str:
    mapping = {
        "malicious": "malicious",
        "phishing": "malicious",
        "suspicious": "suspicious",
        "benign": "benign",
        "恶意": "malicious",
        "可疑": "suspicious",
        "正常": "benign",
    }
    return mapping.get(str(value or "").strip().lower(), "suspicious")


def _normalize_review(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    review = {
        "verdict": _normalize_verdict(str(payload.get("verdict") or "")),
        "score": round(_clip01(payload.get("score"), 0.5), 6),
        "confidence": round(_clip01(payload.get("confidence"), 0.5), 6),
        "attack_types": _safe_list(payload.get("attack_types"), limit=6),
        "reasons": _safe_list(payload.get("reasons"), limit=6),
        "evidence": _safe_list(payload.get("evidence"), limit=8),
        "recommended_action": str(payload.get("recommended_action") or "").strip(),
        "source": "llm",
    }
    if not review["recommended_action"] or not review["reasons"]:
        return {}
    return review


def _fallback_review(context: dict[str, Any]) -> dict[str, Any]:
    parsed_email = context.get("parsed_email", {}) or {}
    url_analysis = context.get("url_analysis", {}) or {}
    url_reputation = context.get("url_reputation", {}) or {}
    plain_body = str(parsed_email.get("plain_body") or parsed_email.get("body") or "").lower()
    html_body = str(parsed_email.get("html_body") or "").lower()
    url_score = _clip01(url_analysis.get("max_possibility"))
    vt_score = _clip01(url_reputation.get("max_risk_score"))

    reasons: list[str] = []
    evidence: list[str] = []
    attack_types: list[str] = []

    if "<script" in html_body or "javascript:" in html_body or "onerror=" in html_body:
        reasons.append("HTML 正文包含主动脚本或高危事件处理器。")
        evidence.append("命中 <script> / javascript: / onerror= 片段。")
        attack_types.append("xss_or_active_content")
    if any(keyword in plain_body for keyword in ["验证账号", "立即登录", "密码", "验证码", "点击链接", "账户停用"]):
        reasons.append("正文包含凭据验证、立即处理或停用威胁等社工话术。")
        evidence.append("命中账号验证、密码、验证码或点击链接等关键词。")
        attack_types.append("credential_phishing")
    if vt_score >= 1.0:
        reasons.append("外部 URL 信誉源已将邮件中的链接标记为高危。")
        evidence.append("VirusTotal URL reputation 命中高危。")
        attack_types.append("malicious_url")

    if vt_score >= 1.0 or "xss_or_active_content" in attack_types:
        verdict = "malicious"
        score = 0.95
        confidence = 0.92
    elif url_score >= 0.75 or attack_types:
        verdict = "suspicious"
        score = 0.72
        confidence = 0.7
    else:
        verdict = "benign"
        score = 0.05
        confidence = 0.85

    if not reasons:
        if url_score > 0:
            reasons = [f"URL 模型最高风险分为 {url_score:.4f}，未达到高风险阈值。"]
        else:
            reasons = ["正文未命中脚本、凭据诱导或 VT 高危 URL 条件。"]
    if not evidence:
        if plain_body.strip():
            evidence = [f"正文长度 {len(plain_body.strip())}，未出现高危关键词命中。"]
        elif html_body.strip():
            evidence = [f"HTML 正文长度 {len(html_body.strip())}，未出现主动脚本片段。"]
        else:
            evidence = ["邮件正文为空。"]

    action_map = {
        "malicious": "立即隔离邮件并阻断用户访问相关链接。",
        "suspicious": "建议人工复核业务上下文并临时隔离相关链接。",
        "benign": "建议归档样本并持续观察相似主题邮件。",
    }
    return {
        "verdict": verdict,
        "score": score,
        "confidence": confidence,
        "attack_types": list(dict.fromkeys(attack_types)),
        "reasons": reasons,
        "evidence": evidence,
        "recommended_action": action_map[verdict],
        "source": "fallback",
    }


def make_content_review_tool(llm) -> AnalysisTool:
    def runner(context: dict[str, Any]) -> dict[str, Any]:
        parsed_email = context.get("parsed_email", {}) or {}
        url_analysis = context.get("url_analysis", {}) or {}
        url_reputation = context.get("url_reputation", {}) or {}
        attachment_analysis = context.get("attachment_analysis", {}) or {}

        review: dict[str, Any] = {}
        if llm is not None:
            prompt = f"""
你是邮件安全分析引擎中的内容复核工具。你只能输出一个 JSON 对象。
要求：
1. verdict 只能是 malicious、suspicious、benign。
2. score/confidence 是 0 到 1 的数字。
3. attack_types、reasons、evidence 必须是数组。
4. recommended_action 必须是一句简体中文建议。
5. 重点识别：凭据窃取、伪登录、社工诱导、主动脚本、恶意链接。

输入：
subject: {parsed_email.get("subject", "")}
plain_body: {str(parsed_email.get("plain_body") or "")[:6000]}
html_body: {str(parsed_email.get("html_body") or "")[:6000]}
url_analysis: {json.dumps(url_analysis, ensure_ascii=False)}
url_reputation: {json.dumps(url_reputation, ensure_ascii=False)}
attachment_analysis: {json.dumps(attachment_analysis, ensure_ascii=False)}

输出格式：
{{
  "verdict": "malicious|suspicious|benign",
  "score": 0.0,
  "confidence": 0.0,
  "attack_types": [],
  "reasons": [],
  "evidence": [],
  "recommended_action": ""
}}
"""
            try:
                response = llm.invoke([SystemMessage(content=prompt)])
                review = _normalize_review(_extract_json_payload(str(getattr(response, "content", "") or "")))
            except Exception:
                review = {}

        if not review:
            review = _fallback_review(context)
        return {"content_review": review}

    return AnalysisTool(
        tool_name="content_review",
        version="1.0.0",
        input_schema={"parsed_email": "dict", "url_analysis": "dict", "url_reputation": "dict", "attachment_analysis": "dict"},
        output_schema={"content_review": "dict"},
        runner=runner,
    )
