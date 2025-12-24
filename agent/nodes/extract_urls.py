
from state.state import EmailAnalysisState
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import re
from models.ollama_llm import llm

def extract_urls(state: EmailAnalysisState):
    """
    Node 2: 使用 LLM 提取并分析 URL
    """

    prompt = f"""
    You are a cybersecurity expert specialized in extracting URLs from email content.  
    Analyze the following email body and extract **only the actual URLs present in it**.

    Email body: {state['body']}

    Instructions:
    1. Extract all URLs, including those hidden in HTML links (e.g., in `href` attributes).
    2. Remove any `http://` or `https://` prefix. Keep only the domain and path (e.g., `domain.com/path`).
    3. **Do NOT include any example URLs from this prompt. Only extract URLs that appear in the email body above.**
    4. Output the result as a comma-separated list inside the <urls> tag. If no URLs are found, output an empty list.

    Output format (this is ONLY a format template — do NOT copy the example domains):
    <urls>
    domain1.com/path,domain2.com,domain3.org/resource
    </urls>

    Now perform the extraction:
    """
    print("提取 URL...")
    response = llm.invoke([SystemMessage(content=prompt)])

    url_pattern = r'<urls>\s*(.*?)\s*</urls>'
    match = re.search(url_pattern, response.content, re.DOTALL)
    urls = []
    # domains = []
    if match:
        print("找到 URL 信息，进行处理...")
        url_str = match.group(1).strip()
        urls = [url.strip() for url in url_str.split(",") if url.strip()]
        print("提取到的 URL:", urls)
        # 去重
        urls = list(set(urls))
        print("去重后 URL:", urls)
        # 剔除前缀http://或https://
        for i in range(len(urls)):
            urls[i] = re.sub(r'^https?://', '', urls[i])
        print("剔除前缀后 URL:", urls)
    return {
        "urls": urls,
        # "domains": domains,
        "execution_trace": state["execution_trace"] + ["extract_urls"]
    }