from functools import lru_cache
from pathlib import Path

import joblib

from backend.workflow.state import EmailAnalysisState
from backend.workflow.nodes.model_output import extract_binary_probabilities


@lru_cache(maxsize=1)
def _load_body_model(model_path: str):
    with open(model_path, "rb") as f:
        return joblib.load(f)



def make_body_reputation_node(model_dir: Path):
    model_path = str(model_dir / "phishing_body.pkl")

    def analyze_body_reputation(state: EmailAnalysisState):
        body = state.get("body", "")
        try:
            model = _load_body_model(model_path)
            prediction = model.predict_proba([body])[0]
        except Exception as exc:
            raise RuntimeError(
                "Failed to load/predict with phishing_body.pkl. "
                "Model artifact version is incompatible with current scikit-learn runtime. "
                "Please run with the original training sklearn version (1.2.2) or retrain/export model under current runtime."
            ) from exc

        phishing_probability, legitimate_probability = extract_binary_probabilities(
            model,
            prediction,
            positive_markers=("phishing", "bad", "malicious"),
        )
        body_analysis = {
            "phishing_probability": phishing_probability,
            "legitimate_probability": legitimate_probability,
            "source": "model",
        }

        return {
            "body_analysis": body_analysis,
            "execution_trace": state["execution_trace"] + ["analyze_body_reputation"],
        }

    return analyze_body_reputation
