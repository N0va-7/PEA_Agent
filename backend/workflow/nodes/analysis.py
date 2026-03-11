from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from backend.workflow.state import EmailAnalysisState


@dataclass(frozen=True)
class DecisionConfig:
    w_url_base: float = 0.4
    w_text_base: float = 0.6
    fusion_threshold: float = 0.79
    body_only_threshold: float = 0.7
    source: str = "defaults"


def _safe_float(value, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed != parsed:
        return default
    return parsed


def _clip01(value: float, default: float) -> float:
    parsed = _safe_float(value, default)
    return min(1.0, max(0.0, parsed))


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _latest_artifact(model_dir: Path, pattern: str) -> Path | None:
    candidates = sorted(model_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _load_decision_config(model_dir: Path, session_factory=None) -> DecisionConfig:
    cfg = DecisionConfig()
    source_parts: list[str] = []

    retrain_report = _latest_artifact(model_dir, "retrain_report_*.json")
    if retrain_report:
        payload = _load_json(retrain_report)
        recommended = payload.get("recommended_backend", {}) if isinstance(payload, dict) else {}
        cfg = DecisionConfig(
            w_url_base=cfg.w_url_base,
            w_text_base=cfg.w_text_base,
            fusion_threshold=_clip01(recommended.get("fusion_threshold_hint"), cfg.fusion_threshold),
            body_only_threshold=_clip01(recommended.get("body_only_threshold"), cfg.body_only_threshold),
            source=cfg.source,
        )
        source_parts.append(retrain_report.name)

    source = ",".join(source_parts) if source_parts else "defaults"
    return DecisionConfig(
        w_url_base=cfg.w_url_base,
        w_text_base=cfg.w_text_base,
        fusion_threshold=cfg.fusion_threshold,
        body_only_threshold=cfg.body_only_threshold,
        source=source,
    )


def _predict_phishing(url_prob: float, text_prob: float, cfg: DecisionConfig) -> float:
    c_u = abs(url_prob - 0.5) + 0.5
    c_t = abs(text_prob - 0.5) + 0.5
    denominator = cfg.w_url_base * c_u + cfg.w_text_base * c_t
    if denominator <= 0:
        w_u = 0.5
    else:
        w_u = (cfg.w_url_base * c_u) / denominator
    w_t = 1 - w_u
    return w_u * url_prob + w_t * text_prob


def make_analysis_node(model_dir: Path, session_factory=None):

    def analyze_email_data(state: EmailAnalysisState):
        cfg = _load_decision_config(model_dir, session_factory=session_factory)
        final_decision = {}
        payload = state.get("payload_analysis", {}) or {}
        payload_level = str(payload.get("level") or "none").lower()
        payload_score = float(payload.get("score") or 0.0)
        payload_summary = str(payload.get("summary") or "").strip()

        if state.get("attachments"):
            if state["attachment_analysis"]["threat_level"] == "malicious":
                final_decision = {
                    "is_malicious": True,
                    "reason": "附件被检测为恶意",
                    "score": 1.0,
                    "config_source": cfg.source,
                }
                return {
                    "final_decision": final_decision,
                    "execution_trace": state["execution_trace"] + ["analyze_email_data"],
                }
            final_decision["reason"] = "附件安全"

        final_decision["reason"] = final_decision.get("reason", "附件不存在")

        if payload_level == "high":
            final_decision = {
                "is_malicious": True,
                "reason": f"{final_decision['reason']}，主题或正文命中高危 payload 规则",
                "score": max(0.99, payload_score),
                "config_source": cfg.source,
                "payload_summary": payload_summary,
            }
            return {
                "final_decision": final_decision,
                "execution_trace": state["execution_trace"] + ["analyze_email_data"],
            }

        if not state.get("body"):
            final_decision["is_malicious"] = False
            final_decision["score"] = 0.0
            final_decision["reason"] += "，无正文，判定为正常"
            final_decision["config_source"] = cfg.source
            if payload_summary:
                final_decision["payload_summary"] = payload_summary
            return {
                "final_decision": final_decision,
                "execution_trace": state["execution_trace"] + ["analyze_email_data"],
            }

        if state.get("body") and state.get("urls"):
            phishing_score = _predict_phishing(
                float(state["url_analysis"].get("max_possibility", 0.0)),
                float(state["body_analysis"].get("phishing_probability", 0.0)),
                cfg,
            )
            final_decision["score"] = phishing_score
            final_decision["config_source"] = cfg.source
            if payload_summary:
                final_decision["payload_summary"] = payload_summary
            if phishing_score > cfg.fusion_threshold:
                final_decision["is_malicious"] = True
                final_decision["reason"] += "，正文和URL综合评分较高，判定为恶意"
            else:
                final_decision["is_malicious"] = False
                final_decision["reason"] += "，正文和URL综合评分较低，判定为正常"
            return {
                "final_decision": final_decision,
                "execution_trace": state["execution_trace"] + ["analyze_email_data"],
            }

        body_score = float(state["body_analysis"].get("phishing_probability", 0.0))
        if body_score > cfg.body_only_threshold:
            final_decision["is_malicious"] = True
            final_decision["score"] = body_score
            final_decision["reason"] += "，无URL且正文评分较高，判定为恶意"
        else:
            final_decision["is_malicious"] = False
            final_decision["score"] = body_score
            final_decision["reason"] += "，无URL且正文评分较低，判定为正常"
        final_decision["config_source"] = cfg.source
        if payload_summary:
            final_decision["payload_summary"] = payload_summary

        return {
            "final_decision": final_decision,
            "execution_trace": state["execution_trace"] + ["analyze_email_data"],
        }

    return analyze_email_data
