from typing import Dict, Tuple
from app.core.config import settings
from app.core.llm.base import BaseLLM
from app.core.llm.providers.openai import OpenAIProvider


LLM_REGISTRY = {
    "openai": OpenAIProvider,
}


# cache instance per (provider, model)
_instances: Dict[Tuple[str, str], BaseLLM] = {}


def create_llm(
    provider: str | None = None,
    model: str | None = None,
    use_cache: bool = True,
) -> BaseLLM:

    provider = provider or settings.CHATBOT_DEFAULT_LLM
    model = model or settings.CHATBOT_DEFAULT_MODEL

    if provider not in LLM_REGISTRY:
        raise ValueError(f"Unsupported LLM provider: {provider}")

    key = (provider, model)

    if use_cache and key in _instances:
        return _instances[key]

    llm_class = LLM_REGISTRY[provider]

    instance = llm_class(
        api_key=settings.CHATBOT_LLM_API_KEYS,
        model=model,
    )

    if use_cache:
        _instances[key] = instance

    return instance
