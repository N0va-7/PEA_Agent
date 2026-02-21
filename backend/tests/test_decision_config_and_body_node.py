import json
from datetime import datetime, timezone

from backend.infra.db import create_engine_and_session, init_db
from backend.models.tables import FusionTuningRun, SystemConfig
from backend.workflow.nodes.analysis import make_analysis_node
from backend.workflow.nodes.body_reputation import make_body_reputation_node


class _FakeBodyModel:
    def predict_proba(self, _rows):
        return [[0.2, 0.8]]


def _base_state():
    return {
        "attachments": [],
        "attachment_analysis": {},
        "body": "hello",
        "urls": [],
        "url_analysis": {},
        "body_analysis": {"phishing_probability": 0.75},
        "execution_trace": [],
    }


def test_body_reputation_keeps_low_score_without_urls(monkeypatch, tmp_path):
    monkeypatch.setattr("backend.workflow.nodes.body_reputation._load_body_model", lambda _path: _FakeBodyModel())
    node = make_body_reputation_node(tmp_path)

    result = node({"body": "hello", "urls": [], "execution_trace": []})

    assert result["body_analysis"]["phishing_probability"] == 0.2
    assert result["body_analysis"]["legitimate_probability"] == 0.8


def test_analysis_node_uses_defaults_when_no_artifacts(tmp_path):
    node = make_analysis_node(tmp_path)
    result = node(_base_state())

    assert result["final_decision"]["is_malicious"] is True
    assert result["final_decision"]["config_source"] == "defaults"


def test_analysis_node_reads_retrain_and_fusion_artifacts(tmp_path):
    retrain_payload = {
        "recommended_backend": {
            "body_only_threshold": 0.9,
            "fusion_threshold_hint": 0.8,
        }
    }
    (tmp_path / "retrain_report_20990101_000000.json").write_text(
        json.dumps(retrain_payload),
        encoding="utf-8",
    )
    fusion_payload = {
        "best": {
            "w_url_base": 1.0,
            "w_text_base": 0.0,
            "threshold": 0.95,
        }
    }
    (tmp_path / "fusion_tuning_latest.json").write_text(
        json.dumps(fusion_payload),
        encoding="utf-8",
    )

    node = make_analysis_node(tmp_path)
    state = _base_state()
    state["urls"] = ["a.test"]
    state["url_analysis"] = {"max_possibility": 0.96}
    state["body_analysis"] = {"phishing_probability": 0.2}

    result = node(state)

    assert result["final_decision"]["is_malicious"] is True
    assert "retrain_report_20990101_000000.json" in result["final_decision"]["config_source"]
    assert "fusion_tuning_latest.json" in result["final_decision"]["config_source"]


def test_analysis_node_prefers_active_tuning_run_from_db(tmp_path):
    engine, session_factory = create_engine_and_session(tmp_path / "analysis.db")
    init_db(engine)
    active_json = tmp_path / "fusion_tuning_active.json"
    active_json.write_text(
        json.dumps(
            {
                "best": {
                    "w_url_base": 1.0,
                    "w_text_base": 0.0,
                    "threshold": 0.95,
                }
            }
        ),
        encoding="utf-8",
    )

    with session_factory() as db:
        run = FusionTuningRun(
            id="run-1",
            status="succeeded",
            triggered_by="admin",
            triggered_at=datetime.now(timezone.utc),
            result_json_path=str(active_json),
            is_active=True,
        )
        db.add(run)
        db.add(SystemConfig(key="active_fusion_tuning_run_id", value="run-1"))
        db.commit()

    node = make_analysis_node(tmp_path, session_factory=session_factory)
    state = _base_state()
    state["urls"] = ["a.test"]
    state["url_analysis"] = {"max_possibility": 0.96}
    state["body_analysis"] = {"phishing_probability": 0.2}

    result = node(state)

    assert result["final_decision"]["is_malicious"] is True
    assert "fusion_tuning_active.json" in result["final_decision"]["config_source"]
