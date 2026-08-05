"""AI model selection and DeepSeek request construction."""

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
