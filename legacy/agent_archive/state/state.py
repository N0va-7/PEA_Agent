from typing import TypedDict, List, Optional, Dict, Any

class EmailAnalysisState(TypedDict):
    # 📥 原始输入
    raw_eml_content: Optional[bytes]

    # 🧹 解析结果
    sender: str
    recipient: str
    subject: str
    body: str
    urls: List[str]
    # domains: List[str]
    attachments: List[Dict[str, Any]]

    # 🔍 分析结果
    url_analysis: Optional[Dict[str, Any]]  # 模型预测结果
    body_analysis: Optional[Dict[str, Any]]  # 引导性语句分析
    attachment_analysis: Optional[Dict[str, Any]]  # 沙箱分析结果

    # 🧠 最终决策
    final_decision: Optional[Dict[str, Any]]
    llm_report: Optional[str]

    # 📊 执行追踪
    execution_trace: List[str]
