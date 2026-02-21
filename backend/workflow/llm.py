from langchain_openai import ChatOpenAI

from backend.infra.config import Settings


def build_llm(settings: Settings):
    if not settings.llm_api_key:
        raise RuntimeError("LLM_API_KEY is required for report generation.")
    return ChatOpenAI(
        model=settings.llm_model_id,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=0.2,
    )
