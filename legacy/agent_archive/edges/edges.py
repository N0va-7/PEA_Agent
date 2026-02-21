from state.state import EmailAnalysisState
from langgraph.graph import StateGraph, END


def route_after_parse_eml(state: EmailAnalysisState) -> str:
    """解析eml和url后的路由决策"""

    if state["attachments"]:
        print("→ 发现附件，进入附件分析流程")
        return "analyze_attachment_reputation"
    else:
        print("→ 未发现附件，检查是否有正文")
        if state["body"]:
            print("→ 发现正文，进入正文分析流程")
            return "analyze_body_reputation"
        else:
            print("→ 邮件为空，流程结束")
            return "analyze_email_data"


def route_after_attachment_analysis(state: EmailAnalysisState) -> str:
    """附件分析后的路由决策"""

    print(f"附件是否恶意: {'是' if state['attachment_analysis']['threat_level'] == 'bad' else '否'}")
    if state["attachment_analysis"]["threat_level"] == "bad":
        print("→ 附件被标记为恶意，流程结束")
        return "analyze_email_data"
    # 附件安全，检查是否存在正文
    if state["body"]:
        print("→ 附件安全，发现正文，进入正文分析流程")
        return "analyze_body_reputation"
    else:
        print("→ 附件安全，未发现正文，流程结束")
        return "analyze_email_data"

def route_after_body_analysis(state: EmailAnalysisState) -> str:
    """正文分析后的路由决策"""

    if state["urls"]:
        print(f"→ 发现{len(state['urls'])}个URL，进入URL分析流程")
        return "analyze_url_reputation"
    else:
        print("→ 未发现URL，流程结束")
        return "analyze_email_data"

def route_after_url_analysis(state: EmailAnalysisState) -> str:
    """URL分析后的路由决策"""

    print(f"URL是否恶意: {'是' if state['url_analysis']['max_possibility'] > 0.8 else '否'}")
    print("→ URL分析完成，流程结束")
    return "analyze_email_data"


