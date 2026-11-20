"""Model factory. Swap providers via .env without touching any chain code."""
from __future__ import annotations

import os

from dotenv import load_dotenv

from .guardrails import llm_max_tokens, llm_timeout

load_dotenv()

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.5-flash",
    "anthropic": "claude-haiku-5-5",
}

KEY_VARS = {
    "openai": "OPENAI_API_KEY",
    "gemini": "GOOGLE_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


def get_provider() -> str:
    """Provider from LLM_PROVIDER (openai | gemini | anthropic | mock)."""
    return os.getenv("LLM_PROVIDER", "openai").strip().lower()


def get_model_name(provider: str | None = None) -> str:
    provider = provider or get_provider()
    return os.getenv("LLM_MODEL") or DEFAULT_MODELS.get(provider, "mock")


def is_mock(provider: str | None = None) -> bool:
    return (provider or get_provider()) == "mock"


def get_llm(provider: str | None = None, temperature: float = 0.0):
    """Return a LangChain chat model for the configured provider.

    The API key is read from the environment (.env) by the provider SDK - it is
    never passed or stored in code.
    """
    provider = provider or get_provider()
    if provider == "mock":
        return None

    key_var = KEY_VARS.get(provider)
    if key_var is None:
        raise ValueError(f"Unknown LLM_PROVIDER '{provider}'. Use openai, gemini, anthropic or mock.")
    if not os.getenv(key_var):
        raise RuntimeError(
            f"{key_var} is not set. Add it to your .env file (see .env.example) "
            "or set LLM_PROVIDER=mock to try the app offline."
        )

    model = get_model_name(provider)
    # Guardrails: cap output tokens and wall-clock time of every request (cost / abuse limits).
    max_tokens, timeout = llm_max_tokens(), llm_timeout()
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model, temperature=temperature, max_retries=2, timeout=timeout,
                          max_tokens=max_tokens)
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(model=model, temperature=temperature, max_retries=2, timeout=timeout,
                                      max_output_tokens=max_tokens)
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(model=model, temperature=temperature, max_retries=2, timeout=timeout,
                         max_tokens=max_tokens)
