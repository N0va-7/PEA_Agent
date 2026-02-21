from backend.workflow.nodes.llm_report import make_llm_report_node


class _DummyResponse:
    def __init__(self, content: str):
        self.content = content


class _GoodLLM:
    def invoke(self, _messages):
        return _DummyResponse(
            """
<json>
{
  "summary": "该邮件存在明显钓鱼诱导特征。",
  "risk_level": "高",
  "key_indicators": ["伪造登录链接", "正文催促立即操作"],
  "recommendations": ["立即隔离", "通知SOC"]
}
</json>
"""
        )


class _FailLLM:
    def invoke(self, _messages):
        raise RuntimeError("llm unavailable")


class _EnglishLLM:
    def invoke(self, _messages):
        return _DummyResponse(
            """
{
  "summary": "Email impersonates a bank and asks for urgent action.",
  "risk_level": "high",
  "key_indicators": ["Suspicious sender", "High phishing URL probability"],
  "recommendations": ["Block sender", "Notify SOC"]
}
"""
        )


def _base_state():
    return {
        "subject": "账户异常提醒",
        "sender": "service@example.com",
        "recipient": "user@example.com",
        "url_analysis": {"max_possibility": 0.91},
        "body_analysis": {"phishing_probability": 0.88},
        "attachment_analysis": {"threat_level": "unknown"},
        "final_decision": {"is_malicious": True, "score": 0.9, "reason": "综合评分较高"},
        "execution_trace": [],
    }


def test_llm_report_node_uses_fixed_markdown_template():
    node = make_llm_report_node(_GoodLLM())
    out = node(_base_state())
    report = out["llm_report"]

    assert "# 邮件威胁分析报告" in report
    assert "## 1. 执行摘要" in report
    assert "## 8. 模型输出快照" in report
    assert "伪造登录链接" in report
    assert "1. 立即隔离" in report
    assert "execution_trace" not in report


def test_llm_report_node_fallbacks_when_llm_fails():
    node = make_llm_report_node(_FailLLM())
    out = node(_base_state())
    report = out["llm_report"]

    assert "# 邮件威胁分析报告" in report
    assert "## 1. 执行摘要" in report
    assert "综合评分较高" in report
    assert out["execution_trace"][-1] == "llm_report"


def test_llm_report_node_rejects_english_sections_and_falls_back_to_chinese():
    node = make_llm_report_node(_EnglishLLM())
    out = node(_base_state())
    report = out["llm_report"]

    assert "Email impersonates a bank" not in report
    assert "Suspicious sender" not in report
    assert "系统综合正文、URL与附件信号后" in report
