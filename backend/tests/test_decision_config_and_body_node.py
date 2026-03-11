import json

from backend.workflow.nodes.analysis import make_analysis_node
from backend.workflow.nodes.body_reputation import make_body_reputation_node
from backend.workflow.nodes.payload_guard import make_payload_guard_node
from backend.workflow.nodes.url_reputation import make_url_reputation_node


class _FakeBodyModel:
    def predict_proba(self, _rows):
        return [[0.2, 0.8]]


class _FakeIntClassesBodyModel:
    classes_ = [0, 1]

    def predict_proba(self, _rows):
        return [[0.8, 0.2]]


class _FakeIntClassesUrlModel:
    classes_ = [0, 1]

    def predict_proba(self, _rows):
        return [[0.7, 0.3]]


def _base_state():
    return {
        "attachments": [],
        "attachment_analysis": {},
        "body": "hello",
        "html_body": "",
        "urls": [],
        "url_analysis": {},
        "body_analysis": {"phishing_probability": 0.75},
        "payload_analysis": {},
        "execution_trace": [],
    }


def test_body_reputation_keeps_low_score_without_urls(monkeypatch, tmp_path):
    monkeypatch.setattr("backend.workflow.nodes.body_reputation._load_body_model", lambda _path: _FakeBodyModel())
    node = make_body_reputation_node(tmp_path)

    result = node({"body": "hello", "urls": [], "execution_trace": []})

    assert result["body_analysis"]["phishing_probability"] == 0.2
    assert result["body_analysis"]["legitimate_probability"] == 0.8


def test_body_reputation_reads_positive_class_from_model_classes(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "backend.workflow.nodes.body_reputation._load_body_model",
        lambda _path: _FakeIntClassesBodyModel(),
    )
    node = make_body_reputation_node(tmp_path)

    result = node({"body": "hello", "urls": [], "execution_trace": []})

    assert result["body_analysis"]["phishing_probability"] == 0.2
    assert result["body_analysis"]["legitimate_probability"] == 0.8


def test_url_reputation_reads_positive_class_from_model_classes(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "backend.workflow.nodes.url_reputation._load_url_model",
        lambda _path: _FakeIntClassesUrlModel(),
    )
    node = make_url_reputation_node(tmp_path)

    result = node({"urls": ["https://example.test"], "execution_trace": []})

    assert result["url_analysis"]["https://example.test"]["phishing_probability"] == 0.3
    assert result["url_analysis"]["https://example.test"]["legitimate_probability"] == 0.7
    assert result["url_analysis"]["max_possibility"] == 0.3


def test_analysis_node_uses_defaults_when_no_artifacts(tmp_path):
    node = make_analysis_node(tmp_path)
    result = node(_base_state())

    assert result["final_decision"]["is_malicious"] is True
    assert result["final_decision"]["config_source"] == "defaults"


def test_analysis_node_reads_retrain_artifact(tmp_path):
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

    node = make_analysis_node(tmp_path)
    state = _base_state()
    state["body_analysis"] = {"phishing_probability": 0.85}

    result = node(state)

    assert result["final_decision"]["is_malicious"] is False
    assert "retrain_report_20990101_000000.json" in result["final_decision"]["config_source"]


def test_payload_guard_hits_high_risk_subject_and_body():
    node = make_payload_guard_node()
    result = node(
        {
            "subject": "<script>alert(1)</script>",
            "body": "<img src=x onerror=alert(1)>",
            "html_body": "",
            "execution_trace": [],
        }
    )

    assert result["payload_analysis"]["level"] == "high"
    assert "script_tag" in result["payload_analysis"]["all_hits"]
    assert "event_handler" in result["payload_analysis"]["all_hits"]


def test_analysis_node_marks_high_payload_as_malicious(tmp_path):
    node = make_analysis_node(tmp_path)
    state = _base_state()
    state["body_analysis"] = {"phishing_probability": 0.1}
    state["payload_analysis"] = {
        "level": "high",
        "score": 0.9,
        "summary": "主题命中高危 payload 规则。",
        "all_hits": ["script_tag"],
    }

    result = node(state)

    assert result["final_decision"]["is_malicious"] is True
    assert "payload" in result["final_decision"]["reason"]
