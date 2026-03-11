from __future__ import annotations

from typing import Any

from backend.agent_tools.base import AnalysisTool


def _clip01(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed != parsed:
        return default
    return min(1.0, max(0.0, parsed))


def _has_strong_content_evidence(content_review: dict[str, Any]) -> bool:
    attack_types = [str(item or "").lower() for item in content_review.get("attack_types", [])]
    evidence = " ".join(str(item or "").lower() for item in content_review.get("evidence", []))
    return any(
        item in {
            "credential_phishing",
            "xss_or_active_content",
            "malicious_url",
            "fake_login_page",
            "凭据窃取",
            "主动脚本",
            "伪登录",
        }
        for item in attack_types
    ) or any(token in evidence for token in ["password", "验证码", "javascript", "伪登录", "credential", "登录", "账号", "密码"])


def make_decision_engine_tool() -> AnalysisTool:
    def runner(context: dict[str, Any]) -> dict[str, Any]:
        url_reputation = context.get("url_reputation", {}) or {}
        url_analysis = context.get("url_analysis", {}) or {}
        content_review = context.get("content_review", {}) or {}
        attachment_analysis = context.get("attachment_analysis", {}) or {}

        url_model_score = _clip01(url_analysis.get("max_possibility"))
        vt_score = _clip01(url_reputation.get("max_risk_score"))
        content_score = _clip01(content_review.get("score"))
        content_verdict = str(content_review.get("verdict") or "benign").lower()
        attachment_verdict = str(attachment_analysis.get("aggregate_verdict") or "unknown").lower()
        high_risk_urls = [str(item) for item in url_reputation.get("high_risk_urls", []) if str(item)]

        decision_trace = [
            {
                "source": "url_reputation_vt",
                "score": vt_score,
                "high_risk_urls": high_risk_urls,
                "cache_sources": [str(item.get("cache_status") or "") for item in url_reputation.get("items", [])],
            },
            {
                "source": "url_model_analysis",
                "score": url_model_score,
            },
            {
                "source": "content_review",
                "verdict": content_verdict,
                "score": content_score,
                "source_type": content_review.get("source", "unknown"),
            },
            {
                "source": "attachment_sandbox",
                "verdict": attachment_verdict,
                "score": _clip01(attachment_analysis.get("score")),
            },
        ]

        if attachment_verdict == "malicious":
            return {
                "decision": {
                    "verdict": "malicious",
                    "score": 1.0,
                    "primary_risk_source": "attachment_sandbox",
                    "reasons": ["附件沙箱明确判定为恶意，直接按恶意邮件处理。"],
                    "decision_trace": decision_trace + [{"source": "decision_engine", "mode": "short_circuit_attachment"}],
                    "recommended_action": "立即隔离邮件并阻断附件传播。",
                }
            }

        if high_risk_urls:
            return {
                "decision": {
                    "verdict": "malicious",
                    "score": 1.0,
                    "primary_risk_source": "vt_url_reputation",
                    "reasons": [f"VirusTotal 已将 URL 标记为高危：{high_risk_urls[0]}"][:1],
                    "decision_trace": decision_trace + [{"source": "decision_engine", "mode": "short_circuit_vt_url"}],
                    "recommended_action": "立即隔离邮件并阻断用户访问高危链接。",
                }
            }

        if content_verdict == "malicious" and _has_strong_content_evidence(content_review):
            return {
                "decision": {
                    "verdict": "malicious",
                    "score": round(max(0.9, content_score, url_model_score), 6),
                    "primary_risk_source": "content_review",
                    "reasons": list(content_review.get("reasons") or ["内容复核发现强恶意信号。"])[:3],
                    "decision_trace": decision_trace + [{"source": "decision_engine", "mode": "content_strong_evidence"}],
                    "recommended_action": str(content_review.get("recommended_action") or "立即隔离邮件并开展人工复核。"),
                }
            }

        verdict = "benign"
        score = round(max(url_model_score, vt_score, content_score * 0.7, _clip01(attachment_analysis.get("score"))), 6)
        primary_risk_source = "none"
        reasons = ["未发现足以支持恶意结论的强信号。"]
        recommended_action = "建议归档样本并持续观察相似邮件。"
        mode = "baseline"

        if attachment_verdict == "suspicious":
            verdict = "suspicious"
            primary_risk_source = "attachment_sandbox"
            score = round(max(score, 0.7), 6)
            reasons = ["附件沙箱返回可疑结论，建议人工复核附件行为。"]
            recommended_action = "建议隔离附件并进行人工复核。"
            mode = "attachment_suspicious"
        elif url_model_score >= 0.75:
            verdict = "suspicious"
            primary_risk_source = "url_model_analysis"
            score = round(max(score, 0.75), 6)
            reasons = ["URL 模型风险分较高，但 VT 未形成直接恶意短路条件。"]
            recommended_action = "建议人工复核链接指向并临时隔离邮件。"
            mode = "url_model_high"
        elif content_verdict == "malicious":
            verdict = "suspicious"
            primary_risk_source = "content_review"
            score = round(max(score, 0.78), 6)
            reasons = list(content_review.get("reasons") or ["内容复核给出恶意倾向，但证据未达到直接恶意短路条件。"])[:3]
            recommended_action = str(content_review.get("recommended_action") or "建议人工复核邮件上下文。")
            mode = "content_malicious_soft"
        elif content_verdict == "suspicious":
            verdict = "suspicious"
            primary_risk_source = "content_review"
            score = round(max(score, 0.6), 6)
            reasons = list(content_review.get("reasons") or ["内容复核存在可疑社工或伪装迹象。"])[:3]
            recommended_action = str(content_review.get("recommended_action") or "建议人工复核邮件上下文。")
            mode = "content_suspicious"

        return {
            "decision": {
                "verdict": verdict,
                "score": score,
                "primary_risk_source": primary_risk_source,
                "reasons": reasons,
                "decision_trace": decision_trace + [{"source": "decision_engine", "mode": mode}],
                "recommended_action": recommended_action,
            }
        }

    return AnalysisTool(
        tool_name="decision_engine",
        version="1.0.0",
        input_schema={"url_reputation": "dict", "url_analysis": "dict", "content_review": "dict", "attachment_analysis": "dict"},
        output_schema={"decision": "dict"},
        runner=runner,
    )
