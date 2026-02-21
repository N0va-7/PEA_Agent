import re

from langchain_core.messages import SystemMessage

from backend.workflow.state import EmailAnalysisState


RAW_URL_PATTERN = re.compile(r"https?://[^\s'\"<>]+", re.IGNORECASE)



def make_extract_urls_node(llm):
    def extract_urls(state: EmailAnalysisState):
        body = state.get("body", "")
        urls = []

        prompt = f"""
You are a cybersecurity expert specialized in extracting URLs from email content.
Analyze the following email body and extract only actual URLs present.
Email body: {body}
Output strictly in format:
<urls>
url1,url2
</urls>
"""
        try:
            response = llm.invoke([SystemMessage(content=prompt)])
            match = re.search(r"<urls>\s*(.*?)\s*</urls>", response.content, re.DOTALL)
            if match:
                url_str = match.group(1).strip()
                urls = [u.strip() for u in url_str.split(",") if u.strip()]
        except Exception:
            urls = []

        if not urls:
            urls = RAW_URL_PATTERN.findall(body)

        normalized = []
        for url in urls:
            normalized.append(re.sub(r"^https?://", "", url.strip()))

        deduped = list(dict.fromkeys([u for u in normalized if u]))

        return {
            "urls": deduped,
            "execution_trace": state["execution_trace"] + ["extract_urls"],
        }

    return extract_urls
