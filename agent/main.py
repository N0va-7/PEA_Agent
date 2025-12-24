import asyncio

from langgraph.checkpoint.memory import InMemorySaver
from state.state import EmailAnalysisState
from nodes.parse_eml import parse_eml_file
from nodes.extract_urls import extract_urls
from nodes.analysis import analyze_email_data
from nodes.attachment_reputation import analyze_attachment_reputation
from nodes.body_reputation import analyze_body_reputation
from nodes.url_reputation import analyze_url_reputation
from nodes.llm_report import llm_report
from nodes.sanitize import sanitize
from edges.edges import *
from langgraph.graph import StateGraph, START, END

def create_email_analysis_workflow():


    # 构建电子邮件分析工作流
    workflow = StateGraph(EmailAnalysisState)

    # 添加两个节点
    workflow.add_node("parse_eml_file", parse_eml_file)
    workflow.add_node("extract_urls", extract_urls)
    workflow.add_node("analyze_attachment_reputation", analyze_attachment_reputation)
    workflow.add_node("analyze_body_reputation", analyze_body_reputation)
    workflow.add_node("analyze_url_reputation", analyze_url_reputation)
    workflow.add_node("analyze_email_data", analyze_email_data)
    workflow.add_node("llm_report", llm_report)
    # workflow.add_node("sanitize", sanitize)


    # 设置线性流程
    workflow.add_edge(START, "parse_eml_file")
    workflow.add_edge("parse_eml_file", "extract_urls")
    workflow.add_conditional_edges(
        "extract_urls",
        route_after_parse_eml,
        {
            "analyze_attachment_reputation": "analyze_attachment_reputation",
            "analyze_body_reputation": "analyze_body_reputation",
            "analyze_email_data": "analyze_email_data"
        }
    )
    workflow.add_conditional_edges(
        "analyze_attachment_reputation",
        route_after_attachment_analysis,
        {
            "analyze_body_reputation": "analyze_body_reputation",
            "analyze_email_data": "analyze_email_data"
        }
    )
    workflow.add_conditional_edges(
        "analyze_body_reputation",
        route_after_body_analysis,
        {
            "analyze_url_reputation": "analyze_url_reputation",
            "analyze_email_data": "analyze_email_data"
        }
    )
    workflow.add_conditional_edges(
        "analyze_url_reputation",
        route_after_url_analysis,
        {
            "analyze_email_data": "analyze_email_data"
        }
    )
    workflow.add_edge("analyze_email_data", "llm_report")
    # workflow.add_edge("llm_report", "sanitize")
    workflow.add_edge("llm_report", END)

    # 编译图
    memory = InMemorySaver()
    app = workflow.compile(checkpointer=memory)

    return app


async def main():
    print("=== 电子邮件分析工作流测试 ===")
    # 创建图实例
    graph = create_email_analysis_workflow()
    print("电子邮件分析工作流已创建。")
    # 读取 EML 文件
    with open("./test/test.eml", "rb") as f:
        eml_content = f.read()
    print("EML 文件已读取。")
    print("开始分析 EML 文件...")
    # 初始化状态
    initial_state = {
        "raw_eml_content": eml_content,
        "sender": "",
        "recipient": "",
        "subject": "",
        "body": "",
        "url_analysis": dict(),
        "domain_analysis": dict(),
        "guidance_analysis": dict(),
        "attachment_analysis": dict(),
        "final_decision": dict(),
        "execution_trace": []
    }
    print("初始状态已设置。")
    print("运行工作流...")
    config = {"configurable": {"thread_id": f"search-session-{0}"}}
    # 运行到 extract_urls 节点
    # result = graph.astream(initial_state, config=config)
    async for output in graph.astream(initial_state, config=config):
        for node_name, node_output in output.items():
            print(f"\n节点: {node_name}")
            # print("输出:")
            # for key, value in node_output.items():
            #     if key != "execution_trace":
            #         print(f"  {key}: {value}")
            # print(f"  execution_trace: {node_output.get('execution_trace', [])}")




if __name__ == "__main__":
    asyncio.run(main())