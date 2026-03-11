from backend.workflow.nodes.decision_engine_v2 import make_decision_engine_v2_node
from backend.workflow.nodes.llm_content_review import make_llm_content_review_node


class _DummyResponse:
    def __init__(self, content: str):
        self.content = content


class _GoodLLM:
    def invoke(self, _messages):
        return _DummyResponse(
            """
{
  "verdict": "malicious",
  "score": 0.96,
  "confidence": 0.93,
  "attack_types": ["credential_phishing"],
  "reasons": ["正文冒充管理员要求立即验证账号。"],
  "evidence": ["邮件要求访问伪造登录入口并输入密码。"],
  "recommended_action": "立即隔离邮件并冻结相关账号。"
}
"""
        )


class _FailLLM:
    def invoke(self, _messages):
        raise RuntimeError("llm unavailable")


def _content_state():
    return {
        "parsed_email": {
            "subject": "账户安全升级通知",
            "plain_body": "请立即登录并验证企业邮箱账号，否则账户将被停用。",
            "body": "请立即登录并验证企业邮箱账号，否则账户将被停用。",
            "html_body": '<html><body><a href="https://login.example.test">verify</a></body></html>',
        },
        "url_analysis": {"max_possibility": 0.82},
        "url_reputation": {"max_risk_score": 0.0, "high_risk_urls": []},
        "attachment_analysis": {"aggregate_verdict": "unknown"},
        "execution_trace": [],
    }


def test_content_review_prefers_llm_output(tmp_path):
    node = make_llm_content_review_node(_GoodLLM(), tmp_path)
    out = node(_content_state())

    assert out["content_review"]["source"] == "llm"
    assert out["content_review"]["verdict"] == "malicious"
    assert out["content_review"]["score"] == 0.96
    assert out["execution_trace"][-1] == "content_review"


def test_content_review_falls_back_to_local_heuristics(tmp_path):
    node = make_llm_content_review_node(_FailLLM(), tmp_path)
    state = _content_state()
    state["parsed_email"]["html_body"] = '<html><body><script>alert(1)</script></body></html>'

    out = node(state)

    assert out["content_review"]["source"] == "fallback"
    assert out["content_review"]["verdict"] == "malicious"
    assert "xss_or_active_content" in out["content_review"]["attack_types"]


def test_decision_engine_short_circuits_malicious_attachment():
    node = make_decision_engine_v2_node()
    out = node(
        {
            "url_reputation": {"max_risk_score": 0.0, "high_risk_urls": []},
            "url_analysis": {"max_possibility": 0.0},
            "content_review": {"verdict": "benign"},
            "attachment_analysis": {"aggregate_verdict": "malicious", "score": 1.0},
            "execution_trace": [],
        }
    )

    assert out["decision"]["verdict"] == "malicious"
    assert out["decision"]["primary_risk_source"] == "attachment_sandbox"


def test_decision_engine_short_circuits_vt_high_risk_url():
    node = make_decision_engine_v2_node()
    out = node(
        {
            "url_reputation": {"max_risk_score": 1.0, "high_risk_urls": ["https://evil.test/login"], "items": []},
            "url_analysis": {"max_possibility": 0.1},
            "content_review": {"verdict": "benign", "score": 0.1},
            "attachment_analysis": {"aggregate_verdict": "unknown", "score": 0.0},
            "execution_trace": [],
        }
    )

    assert out["decision"]["verdict"] == "malicious"
    assert out["decision"]["score"] == 1.0
    assert out["decision"]["primary_risk_source"] == "vt_url_reputation"
    assert "evil.test" in out["decision"]["reasons"][0]
    assert out["decision"]["decision_trace"][-1]["mode"] == "short_circuit_vt_url"


def test_decision_engine_marks_high_url_model_without_vt_as_suspicious():
    node = make_decision_engine_v2_node()
    out = node(
        {
            "url_reputation": {"max_risk_score": 0.0, "high_risk_urls": [], "items": []},
            "url_analysis": {"max_possibility": 0.82},
            "content_review": {"verdict": "benign", "score": 0.2},
            "attachment_analysis": {"aggregate_verdict": "unknown", "score": 0.0},
            "execution_trace": [],
        }
    )

    assert out["decision"]["verdict"] == "suspicious"
    assert out["decision"]["primary_risk_source"] == "url_model_analysis"


def test_decision_engine_promotes_malicious_content_with_cn_attack_types():
    node = make_decision_engine_v2_node()
    out = node(
        {
            "url_reputation": {"max_risk_score": 0.0, "high_risk_urls": [], "items": []},
            "url_analysis": {"max_possibility": 0.91},
            "content_review": {
                "verdict": "malicious",
                "score": 0.95,
                "attack_types": ["凭据窃取", "伪登录"],
                "reasons": ["邮件诱导用户点击登录链接并输入账号密码。"],
                "evidence": ["请立即登录并验证账号密码。"],
                "recommended_action": "立即隔离邮件。",
            },
            "attachment_analysis": {"aggregate_verdict": "unknown", "score": 0.0},
            "execution_trace": [],
        }
    )

    assert out["decision"]["verdict"] == "malicious"
    assert out["decision"]["primary_risk_source"] == "content_review"
