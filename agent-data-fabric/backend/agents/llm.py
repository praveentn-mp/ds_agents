"""LLM factory — Azure OpenAI (primary) / Ollama (fallback) with token tracking."""

import time
from dataclasses import dataclass, field
from typing import Optional
from backend.config import settings


@dataclass
class LLMUsage:
    model: str = ""
    tokens_input: int = 0
    tokens_output: int = 0
    tokens_cache: int = 0
    latency_ms: int = 0


def get_llm():
    if settings.use_azure_openai:
        from langchain_openai import AzureChatOpenAI
        return AzureChatOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.api_version,
            azure_deployment=settings.azure_deployment,
            temperature=0,
            streaming=True,
        )
    else:
        from langchain_community.chat_models import ChatOllama
        return ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            temperature=0,
        )


async def invoke_llm(prompt: str) -> tuple[str, LLMUsage]:
    """Invoke LLM and return (response_text, usage_info)."""
    llm = get_llm()
    model_name = get_model_name()
    start = time.monotonic()

    response = await llm.ainvoke(prompt)
    latency = int((time.monotonic() - start) * 1000)

    usage = LLMUsage(model=model_name, latency_ms=latency)

    # Extract token usage from response metadata if available
    meta = getattr(response, "response_metadata", {}) or {}
    token_usage = meta.get("token_usage") or meta.get("usage") or {}
    if token_usage:
        usage.tokens_input = token_usage.get("prompt_tokens", 0) or token_usage.get("input_tokens", 0)
        usage.tokens_output = token_usage.get("completion_tokens", 0) or token_usage.get("output_tokens", 0)
        usage.tokens_cache = token_usage.get("cached_tokens", 0)
    else:
        # Estimate from content length if no metadata
        usage.tokens_input = len(prompt) // 4
        usage.tokens_output = len(response.content) // 4

    return response.content, usage


def get_model_name() -> str:
    if settings.use_azure_openai:
        return settings.azure_deployment
    return settings.ollama_model
