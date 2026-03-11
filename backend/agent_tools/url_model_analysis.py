from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib

from backend.agent_tools.base import AnalysisTool
from backend.workflow.nodes.model_output import extract_binary_probabilities


@lru_cache(maxsize=1)
def _load_url_model(model_path: str):
    with open(model_path, "rb") as handle:
        return joblib.load(handle)


def _model_input(url: str) -> str:
    return re.sub(r"^https?://", "", str(url or "").strip(), flags=re.IGNORECASE)


def make_url_model_analysis_tool(model_dir: Path) -> AnalysisTool:
    model_path = str(model_dir / "phishing_url.pkl")

    def runner(context: dict[str, Any]) -> dict[str, Any]:
        extraction = context.get("url_extraction", {}) or {}
        urls = [str(item) for item in extraction.get("normalized_urls", []) if str(item)]
        items: list[dict[str, Any]] = []

        try:
            model = _load_url_model(model_path)
        except Exception as exc:
            raise RuntimeError(
                "Failed to load phishing_url.pkl. "
                "Model artifact version is incompatible with current scikit-learn runtime."
            ) from exc

        max_possibility = 0.0
        for url in urls:
            try:
                prediction = model.predict_proba([_model_input(url)])[0]
            except Exception as exc:
                raise RuntimeError(
                    "Failed to predict with phishing_url.pkl. "
                    "Model artifact version is incompatible with current scikit-learn runtime."
                ) from exc
            phishing_probability, legitimate_probability = extract_binary_probabilities(
                model,
                prediction,
                positive_markers=("phishing", "bad", "malicious"),
            )
            max_possibility = max(max_possibility, float(phishing_probability))
            items.append(
                {
                    "url": url,
                    "phishing_probability": round(float(phishing_probability), 6),
                    "legitimate_probability": round(float(legitimate_probability), 6),
                    "source": "model",
                }
            )

        return {
            "url_analysis": {
                "items": items,
                "max_possibility": round(max_possibility, 6),
                "summary": "未提取到 URL" if not items else f"URL 模型最高风险分 {max_possibility:.4f}",
            }
        }

    return AnalysisTool(
        tool_name="url_model_analysis",
        version="1.0.0",
        input_schema={"url_extraction": "dict"},
        output_schema={"url_analysis": "dict"},
        runner=runner,
    )
