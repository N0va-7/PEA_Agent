from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

from backend.models.tables import FusionTuningRun, SystemConfig
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


def _resolve_active_tuning_path(model_dir: Path, session_factory=None) -> Path | None:
    if session_factory is None:
        return None

    try:
        with session_factory() as db:
            cfg = db.get(SystemConfig, "active_fusion_tuning_run_id")
            if not cfg or not cfg.value:
                return None
            run = db.execute(
                select(FusionTuningRun)
                .where(FusionTuningRun.id == cfg.value)
                .where(FusionTuningRun.status == "succeeded")
                .limit(1)
            ).scalar_one_or_none()
            if not run or not run.result_json_path:
                return None
            path = Path(run.result_json_path)
            if not path.exists():
                fallback = model_dir / path.name
                return fallback if fallback.exists() else None
            return path
    except Exception:
        return None


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

    fusion_tuning = _resolve_active_tuning_path(model_dir, session_factory=session_factory)
    if fusion_tuning is None:
        fusion_tuning = _latest_artifact(model_dir, "fusion_tuning*.json")
    if fusion_tuning:
        payload = _load_json(fusion_tuning)
        best = payload.get("best", {}) if isinstance(payload, dict) else {}
        w_url_base = _clip01(best.get("w_url_base"), cfg.w_url_base)
        w_text_base = _clip01(best.get("w_text_base"), cfg.w_text_base)
        total = w_url_base + w_text_base
        if total <= 0:
            w_url_base, w_text_base = cfg.w_url_base, cfg.w_text_base
        else:
            w_url_base /= total
            w_text_base /= total
        cfg = DecisionConfig(
            w_url_base=w_url_base,
            w_text_base=w_text_base,
            fusion_threshold=_clip01(best.get("threshold"), cfg.fusion_threshold),
            body_only_threshold=cfg.body_only_threshold,
            source=cfg.source,
        )
        source_parts.append(fusion_tuning.name)

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

        if state.get("attachments"):
            if state["attachment_analysis"]["threat_level"] == "bad":
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

        if not state.get("body"):
            final_decision["is_malicious"] = False
            final_decision["score"] = 0.0
            final_decision["reason"] += "，无正文，判定为正常"
            final_decision["config_source"] = cfg.source
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

        return {
            "final_decision": final_decision,
            "execution_trace": state["execution_trace"] + ["analyze_email_data"],
        }

    return analyze_email_data
