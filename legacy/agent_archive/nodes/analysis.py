
from state.state import EmailAnalysisState
from models.ollama_llm import llm


def predict_phishing(url_prob, text_prob):
    print("计算正文和URL的综合恶意概率...")
    # 基础权重
    w_u_base = 0.6
    w_t_base = 0.4
    print("计算动态权重...")
    # 置信度因子
    c_u = abs(url_prob - 0.5) + 0.5
    c_t = abs(text_prob - 0.5) + 0.5
    print("计算最终权重...")
    # 动态权重
    w_u = (w_u_base * c_u) / (w_u_base * c_u + w_t_base * c_t)
    w_t = 1 - w_u
    print(f"URL权重: {w_u}, 正文权重: {w_t}")
    final_prob = w_u * url_prob + w_t * text_prob
    return final_prob


def analyze_email_data(state: EmailAnalysisState):
    """
    Node: 综合分析邮件数据
    :param state:
    :return:
    """
    print("综合分析邮件数据...")
    final_decision = dict()
    # 如果附件存在
    if state["attachments"]:
        print("→ 发现附件，检查附件分析结果...")
        # 判断是否是恶意
        if state["attachment_analysis"]["threat_level"] == "bad":
            final_decision = {
                "is_malicious": True,
                "reason": "附件被检测为恶意"
            }
            print("→ 附件被检测为恶意，判定为恶意邮件")
            return {
                "final_decision": final_decision,
                "execution_trace": state["execution_trace"] + ["analyze_email_data"]
            }
        final_decision["reason"] = "附件安全"
        print("→ 附件被检测为安全，继续分析正文和URL...")
    final_decision["reason"] = final_decision.get("reason", "附件不存在")
    print("附件分析结果:", final_decision["reason"])
    # 无附件或者附件非恶意，那么继续分析正文结果
    # body 不存在
    if state["body"] is None or state["body"] == "":
        print("→ 未发现正文，判定为正常邮件")
        final_decision["is_malicious"] = False
        final_decision["reason"] += "，无正文，判定为正常"
        return {
            "final_decision": final_decision,
            "execution_trace": state["execution_trace"] + ["analyze_email_data"]
        }
    # 如果 body 存在且 urls 也存在
    if state["body"] and state["urls"]:
        print("→ 发现正文和URL，综合分析正文和URL结果...")
        # 综合正文和 URL 分析结果
        phishing_score = predict_phishing(
            state["url_analysis"]["max_possibility"],
            state["body_analysis"]["phishing_probability"]
        )
        print("综合评分:", phishing_score)
        if phishing_score > 0.5:
            final_decision["is_malicious"] = True
            final_decision["reason"] += "，正文和URL综合评分较高，判定为恶意"
        else:
            final_decision["is_malicious"] = False
            final_decision["reason"] += "，正文和URL综合评分较低，判定为正常"
        print("最终判定:", final_decision["reason"])
        return {
            "final_decision": final_decision,
            "execution_trace": state["execution_trace"] + ["analyze_email_data"]
        }
    # 仅存在 body
    if state["body"] != "":
        print("→ 仅发现正文，分析正文结果...")
        if state["body_analysis"]["phishing_probability"] > 0.7:
            final_decision["is_malicious"] = True
            final_decision["reason"] += "，无url且正文评分较高，判定为恶意"
        else:
            final_decision["is_malicious"] = False
            final_decision["reason"] += "，无url且正文评分较低，判定为正常"
        print("最终判定:", final_decision["reason"])
        return {
            "final_decision": final_decision,
            "execution_trace": state["execution_trace"] + ["analyze_email_data"]
        }