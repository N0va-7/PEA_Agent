import streamlit as st
import asyncio
from typing import Dict, Any


# --- 1. 定义你的状态结构 (仅用于类型提示，Streamlit不需要重新定义类) ---
from state.state import EmailAnalysisState
from main import create_email_analysis_workflow

# --- 2. 页面配置 ---
st.set_page_config(
    page_title="恶意邮件检测智能体",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS美化 (可选，让界面更专业) ---
# --- 样式优化 ---
st.markdown("""
<style>
    .stMetric {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #dee2e6;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    /* 让日志区域更好看 */
    .stCode {
        font-family: 'Consolas', 'Courier New', monospace !important;
        font-size: 0.9em;
    }
</style>
""", unsafe_allow_html=True)


# --- 核心异步处理函数 ---
async def run_analysis_pipeline(file_bytes: bytes, status_container):
    """
    驱动 LangGraph 并根据日志结构实时更新 UI
    """
    # 1. 创建工作流
    try:
        app = create_email_analysis_workflow()
    except Exception as e:
        st.error(f"❌ 初始化失败: {str(e)}")
        return

    # 2. 初始化状态 (根据你的日志，初始状态包含 raw_eml_content)
    initial_state = {
        "raw_eml_content": file_bytes,
        "sender": "",
        "recipient": "",
        "subject": "",
        "body": "",
        "url_analysis": {},
        "body_analysis": {},
        "attachment_analysis": {},
        "final_decision": {},
        "execution_trace": []
    }

    config = {"configurable": {"thread_id": "web-session-live"}}

    # === UI 占位符初始化 ===

    st.markdown("### 📊 实时检测仪表盘")
    # 创建三个指标卡片
    m_col1, m_col2, m_col3 = st.columns(3)
    with m_col1:
        att_metric = st.empty()
        att_metric.metric("附件威胁度", "等待检测...", border=True)
    with m_col2:
        body_metric = st.empty()
        body_metric.metric("正文钓鱼概率", "等待检测...", border=True)
    with m_col3:
        url_metric = st.empty()
        url_metric.metric("URL钓鱼概率", "等待检测...", border=True)

    st.markdown("---")

    # 报告与日志区域
    report_container = st.empty()

    st.subheader("🕵️‍♂️ Agent 思考与执行日志")
    log_area = st.empty()
    logs = []

    # 3. 启动异步流
    try:
        async for output in app.astream(initial_state, config=config):

            for node_name, state_update in output.items():

                # --- 通用日志更新 ---
                # 记录节点完成信息
                logs.append(f"✅ 完成节点: {node_name}")

                # 根据不同节点提取关键信息展示在日志里
                if node_name == "extract_urls":
                    urls = state_update.get("urls", [])
                    logs.append(f"   -> 提取到 {len(urls)} 个 URL")

                # 实时刷新日志框
                log_area.code("\n".join(logs), language="text")
                status_container.update(label=f"正在运行: {node_name}...", state="running")

                # --- 针对具体节点更新 UI 指标 (数据清洗) ---

                # 1. 附件分析 (analyze_attachment_reputation)
                if node_name == "analyze_attachment_reputation":
                    # 日志显示结构: {'文件名': {'threat_level': 'unknown', ...}}
                    att_data = state_update.get("attachment_analysis", {})

                    if not att_data:
                        att_metric.metric("附件威胁度", "无附件", delta="安全")
                    else:
                        # 遍历附件，取第一个或最危险的一个
                        for fname, info in att_data.items():
                            level = info.get("threat_level", "unknown")
                            engines = info.get("multi_engines", "0/0")

                            # 简单的颜色逻辑
                            is_safe = level in ["clean", "unknown"] and "0/" in engines

                            att_metric.metric(
                                label="附件威胁度 (微步沙箱)",
                                value=level.upper(),  # 显示 UNKNOWN / MALICIOUS
                                delta=f"引擎: {engines}",
                                delta_color="normal" if is_safe else "inverse"
                            )
                            break  # 只显示第一个，避免刷屏

                # 2. 正文分析 (analyze_body_reputation)
                elif node_name == "analyze_body_reputation":
                    # 日志显示: {'phishing_probability': 0.6, ...}
                    body_data = state_update.get("body_analysis", {})
                    prob = body_data.get("phishing_probability", 0)

                    body_metric.metric(
                        label="正文钓鱼概率 (RF模型)",
                        value=f"{prob * 100:.1f}%",
                        delta="偏高" if prob > 0.5 else "正常",
                        delta_color="inverse"
                    )

                # 3. URL 分析 (analyze_url_reputation)
                elif node_name == "analyze_url_reputation":
                    # 日志显示: {'phishing_probability': 0.299...}
                    url_data = state_update.get("url_analysis", {})

                    prob = url_data.get("max_possibility", 0)

                    url_metric.metric(
                        label="URL钓鱼概率 (LR模型)",
                        value=f"{prob * 100:.1f}%",
                        delta="高危" if prob > 0.5 else "安全",
                        delta_color="inverse"
                    )

                # 4. 最终决策 (analyze_email_data)
                elif node_name == "analyze_email_data":
                    # 你的日志显示: "综合评分: 0.408", "最终判定: ..."
                    final_data = state_update.get("final_decision", {})
                    verdict = final_data.get("is_malicious", False)
                    logs.append(f"   -> 综合研判完成，结果: {'恶意' if verdict else '安全'}")
                    log_area.code("\n".join(logs), language="text")

                # 5. LLM 报告 (llm_report)
                elif node_name == "llm_report":
                    report_content = state_update.get("llm_report", "")

                    report_container.subheader("📝 最终安全研判报告")
                    report_container.markdown(report_content)

                    # 状态完结
                    status_container.update(label="✅ 分析完成", state="complete", expanded=False)

    except Exception as e:
        st.error(f"❌ 运行过程中发生错误: {str(e)}")
        # 打印详细堆栈以便调试
        import traceback
        st.code(traceback.format_exc())
        status_container.update(label="❌ 运行出错", state="error")


# --- 主界面逻辑 ---

st.title("🛡️ 邮件安全智能防御系统")
st.caption("基于 LangGraph 动态编排 | 逻辑回归 URL 检测 | 随机森林正文检测 | 微步在线沙箱")

# 侧边栏
with st.sidebar:
    st.header("1. 样本上传")
    uploaded_file = st.file_uploader("请上传 .eml 文件", type=['eml'])

    st.divider()

    st.header("2. 控制面板")
    start_btn = st.button("🚀 开始深度分析", type="primary", use_container_width=True)

# 触发逻辑
if start_btn:
    if uploaded_file is None:
        st.warning("⚠️ 请先上传文件")
    else:
        file_bytes = uploaded_file.getvalue()
        # 创建状态容器
        status_box = st.status("正在初始化智能体...", expanded=True)
        # 运行
        asyncio.run(run_analysis_pipeline(file_bytes, status_box))