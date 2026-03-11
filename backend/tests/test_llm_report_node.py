from backend.agent_tools.report_renderer import make_report_renderer_tool


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
  "key_indicators": ["伪造登录链接", "正文催促立即操作"],
  "recommendations": ["立即隔离", "通知SOC"]
}
</json>
"""
        )


class _FailLLM:
    def invoke(self, _messages):
        raise RuntimeError("llm unavailable")


def _base_context():
    return {
        "parsed_email": {
            "subject": "账户异常提醒",
            "sender": "service@example.com",
            "recipient": "user@example.com",
        },
        "url_reputation": {"max_risk_score": 1.0, "high_risk_urls": ["https://evil.test/login"]},
        "url_analysis": {"max_possibility": 0.91},
        "content_review": {"verdict": "malicious", "score": 0.9},
        "attachment_analysis": {"aggregate_verdict": "unknown"},
        "decision": {"verdict": "malicious", "score": 1.0, "primary_risk_source": "vt_url_reputation"},
    }


def test_report_renderer_uses_fixed_markdown_template():
    tool = make_report_renderer_tool(_GoodLLM())
    out = tool.run(_base_context())
    report = out["report"]["markdown"]

    assert "# 邮件威胁分析报告" in report
    assert "## 1. 执行摘要" in report
    assert "## 6. 模型输出快照" in report
    assert "伪造登录链接" in report
    assert "1. 立即隔离" in report


def test_report_renderer_falls_back_when_llm_fails():
    tool = make_report_renderer_tool(_FailLLM())
    out = tool.run(_base_context())
    report = out["report"]["markdown"]

    assert "# 邮件威胁分析报告" in report
    assert "VT 高危 URL：https://evil.test/login" in report
    assert "vt_url_reputation" in report
    assert "保留样本证据链并跟踪相似主题邮件" not in report
