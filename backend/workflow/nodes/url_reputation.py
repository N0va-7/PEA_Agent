from functools import lru_cache
from pathlib import Path

import joblib

from backend.workflow.state import EmailAnalysisState


@lru_cache(maxsize=1)
def _load_url_model(model_path: str):
    with open(model_path, "rb") as f:
        return joblib.load(f)



def make_url_reputation_node(model_dir: Path):
    model_path = str(model_dir / "phishing_url.pkl")

    def analyze_url_reputation(state: EmailAnalysisState):
        urls = state.get("urls", [])
        url_analysis = {}
        try:
            model = _load_url_model(model_path)
        except Exception as exc:
            raise RuntimeError(
                "Failed to load phishing_url.pkl. "
                "Model artifact version is incompatible with current scikit-learn runtime. "
                "Please run with the original training sklearn version (1.2.2) or retrain/export model under current runtime."
            ) from exc

        for url in urls:
            try:
                prediction = model.predict_proba([url])[0]
            except Exception as exc:
                raise RuntimeError(
                    "Failed to predict with phishing_url.pkl. "
                    "Model artifact version is incompatible with current scikit-learn runtime. "
                    "Please run with the original training sklearn version (1.2.2) or retrain/export model under current runtime."
                ) from exc
            url_analysis[url] = {
                "phishing_probability": float(prediction[0]),
                "legitimate_probability": float(prediction[1]),
                "source": "model",
            }

        if urls:
            url_analysis["max_possibility"] = max(url_analysis[url]["phishing_probability"] for url in urls)
        else:
            url_analysis["max_possibility"] = 0.0

        return {
            "url_analysis": url_analysis,
            "execution_trace": state["execution_trace"] + ["analyze_url_reputation"],
        }

    return analyze_url_reputation
