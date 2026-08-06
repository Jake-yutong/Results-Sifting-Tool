"""AI model selection and DeepSeek request construction."""

import json
import time

import anthropic
import httpx
import openai
from openai import OpenAI

DEFAULT_AI_MODEL = "deepseek-v4-pro"
SUPPORTED_AI_MODELS = {
    DEFAULT_AI_MODEL,
    "deepseek-v4-flash",
    "minimax",
}

DEEPSEEK_SYSTEM_PROMPT = (
    'You are a paper screening assistant. Output ONLY valid JSON: '
    '{"exclude": true/false, "reason": "text"}. Be concise.'
)


def normalize_ai_model(value):
    """Return a supported model identifier, defaulting safely to V4 Pro."""
    return value if value in SUPPORTED_AI_MODELS else DEFAULT_AI_MODEL


def create_deepseek_completion(client, model, prompt):
    """Create a non-streaming DeepSeek V4 screening completion."""
    return client.chat.completions.create(
        model=normalize_ai_model(model),
        messages=[
            {"role": "system", "content": DEEPSEEK_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}},
        stream=False,
    )


def check_ai_connection(api_key, model):
    """Send a minimal provider request and return model and latency details."""
    selected_model = normalize_ai_model(model)
    started_at = time.perf_counter()

    if selected_model == "minimax":
        client = anthropic.Anthropic(
            api_key=api_key,
            base_url="https://api.minimaxi.com/anthropic",
            timeout=httpx.Timeout(15.0, connect=5.0),
        )
        client.messages.create(
            model="MiniMax-M2.1",
            max_tokens=8,
            system="Reply with OK only.",
            messages=[{"role": "user", "content": "Connection test"}],
        )
    else:
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
            timeout=httpx.Timeout(15.0, connect=5.0),
            max_retries=0,
        )
        client.chat.completions.create(
            model=selected_model,
            messages=[
                {"role": "system", "content": "Reply with OK only."},
                {"role": "user", "content": "Connection test"},
            ],
            max_tokens=8,
            extra_body={"thinking": {"type": "disabled"}},
            stream=False,
        )

    return {
        "model": selected_model,
        "latency_ms": round((time.perf_counter() - started_at) * 1000),
    }


def classify_ai_error(error):
    """Map provider failures to safe HTTP status, category, and message."""
    if isinstance(error, json.JSONDecodeError):
        return 502, "invalid_response", "The AI provider returned an invalid response."

    timeout_types = (
        httpx.TimeoutException,
        openai.APITimeoutError,
        anthropic.APITimeoutError,
    )
    if isinstance(error, timeout_types):
        return 503, "timeout", "The AI provider timed out. Try again."

    connection_types = (
        httpx.ConnectError,
        openai.APIConnectionError,
        anthropic.APIConnectionError,
    )
    if isinstance(error, connection_types):
        return (
            503,
            "network_error",
            "Cannot reach the AI provider. Check network access and proxy settings.",
        )

    status_code = getattr(error, "status_code", None)
    if status_code == 401:
        return 401, "invalid_api_key", "The API key is invalid or unauthorized."
    if status_code == 402:
        return 402, "insufficient_balance", "The API account has insufficient balance."
    if status_code == 429:
        return 429, "rate_limited", "The API rate limit was reached. Try again later."
    if isinstance(status_code, int):
        return 502, "provider_error", "The AI provider rejected the request."

    return 500, "unexpected_error", "The AI request failed unexpectedly."
