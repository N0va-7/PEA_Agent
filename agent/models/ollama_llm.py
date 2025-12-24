import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

def get_llm():
    # 加载 .env 文件中的环境变量
    load_dotenv()

    # 初始化模型
    # 我们将使用这个 llm 实例来驱动所有节点的智能
    llm = ChatOpenAI(
        model=os.getenv("LLM_MODEL_ID", "gpt-4o-mini"),
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
        temperature=0.7
    )
    return llm

llm = get_llm()