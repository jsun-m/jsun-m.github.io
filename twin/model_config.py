"""The twin's LLM seam (agentos model_config.py pattern).

Switch providers with env, no code changes:
    TWIN_PROVIDER = gemini (default) | deepseek | openai
    TWIN_MODEL    = optional model override for the chosen provider
Key env per provider: GEMINI_API_KEY / DEEPSEEK_API_KEY / OPENAI_API_KEY.
"""

import os

from ag2.config import GeminiConfig, OpenAIConfig

DEFAULT_MODELS = {
    "gemini": "gemini-3.5-flash",
    "deepseek": "deepseek-chat",
    "openai": "gpt-4o",
}

PROVIDER = os.environ.get("TWIN_PROVIDER", "gemini").lower()
MODEL = os.environ.get("TWIN_MODEL") or DEFAULT_MODELS.get(PROVIDER, "")

MAX_OUTPUT_TOKENS = 2048


def build_model_config(*, streaming: bool = True):
    key = os.environ.get(f"{PROVIDER.upper()}_API_KEY", "")
    if PROVIDER == "gemini":
        return GeminiConfig(
            MODEL,
            api_key=key,
            streaming=streaming,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
    if PROVIDER == "deepseek":
        return OpenAIConfig(
            MODEL,
            api_key=key,
            base_url="https://api.deepseek.com",
            streaming=streaming,
            max_tokens=MAX_OUTPUT_TOKENS,
        )
    if PROVIDER == "openai":
        return OpenAIConfig(
            MODEL,
            api_key=key,
            streaming=streaming,
            max_tokens=MAX_OUTPUT_TOKENS,
        )
    raise RuntimeError(f"unknown TWIN_PROVIDER: {PROVIDER!r} (gemini | deepseek | openai)")
