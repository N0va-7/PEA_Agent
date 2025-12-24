from state.state import EmailAnalysisState
from models.ollama_llm import llm
from langchain_core.messages import SystemMessage
import re

def llm_report(state: EmailAnalysisState):
    """
    Node: 使用 LLM 生成综合分析报告
    """
    print("LLM生成综合分析报告...")
    prompt = f"""
    You are a senior cybersecurity analyst specializing in phishing and malware detection.  
    Generate a standardized email threat analysis report in **Chinese**, strictly following the structure below.

    Input data:
    - Email Subject: {state['subject']}
    - Sender: {state['sender']}
    - Recipient: {state['recipient']}
    - URL Analysis: {state.get('url_analysis', {})}
    - Body Analysis: {state.get('body_analysis', {})}
    - Attachment Analysis: {state.get('attachment_analysis', {})}
    - Final Decision: {state.get('final_decision', {})}

    Instructions:
    1. Write the entire report in **Chinese**.
    2. Use professional, concise language suitable for enterprise security teams.
    3. Do NOT add any content outside the specified sections.
    4. Output ONLY the content between <report> and </report>, in valid Markdown format.
    5. The important data is finally determined by the "Final Decision" section; use it to guide your overall assessment.
    6. Follow this exact structure:

    <report>
    ## 邮件基本信息
    - **主题**：[邮件主题]
    - **发件人**：[发件人邮箱]
    - **收件人**：[收件人邮箱]

    ## 综合判定结果
    - **是否恶意**：[是 / 否]
    - **置信度**：[高 / 中 / 低]（基于最终决策中的置信分数）
    - **判定依据**：[1~2句话总结关键依据]

    ## 威胁详情分析
    ### 正文分析
    - 钓鱼概率：[数值或“未分析”]
    - 风险描述：[简要说明，如“包含诱导性话术”或“无异常”]

    ### 链接分析
    - 检测链接：[列出所有URL，若无则写“无”]
    - 风险等级：[安全 / 可疑 / 恶意]
    - 分析说明：[如“信誉良好”]

    ### 附件分析
    - 附件名称：[文件名，若无则写“无附件”]
    - 威胁等级：[安全 / 未知 / 恶意]
    - 检测结果：[如“0/28 引擎报警，沙箱未发现行为异常”]

    ## 安全建议
    - [建议1，具体可操作]
    - [建议2]
    - [建议3，如适用]

    </report>
    """
    print("生成报告中...")
    response = llm.invoke([SystemMessage(content=prompt)])
    print("报告生成完成，提取内容...")
    report_pattern = r'<report>\s*(.*?)\s*</report>'
    match = re.search(report_pattern, response.content, re.DOTALL)

    report = ""
    if match:
        print("找到报告内容，进行处理...")
        report = match.group(1).strip()
        print("提取到的报告内容:", report)
        # 保存到reports目录下
        with open('./reports/email_report.md', 'w', encoding='utf-8') as f:
            f.write(report)
    return {
        "llm_report": report,
        "execution_trace": state["execution_trace"] + ["llm_report"]
    }