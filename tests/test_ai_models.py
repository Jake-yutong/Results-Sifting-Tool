import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from ai_models import (
    check_ai_connection,
    classify_ai_error,
    create_deepseek_completion,
    normalize_ai_model,
)


class RecordingCompletions:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(choices=[])


class RecordingMessages(RecordingCompletions):
    pass


class ProviderStatusError(Exception):
    def __init__(self, status_code):
        super().__init__(f"provider status {status_code}")
        self.status_code = status_code


class DeepSeekModelsTest(unittest.TestCase):
    def test_normalizes_supported_models_and_defaults_unknown_values(self):
        self.assertEqual(normalize_ai_model("deepseek-v4-pro"), "deepseek-v4-pro")
        self.assertEqual(normalize_ai_model("deepseek-v4-flash"), "deepseek-v4-flash")
        self.assertEqual(normalize_ai_model("minimax"), "minimax")
        self.assertEqual(normalize_ai_model("deepseek"), "deepseek-v4-pro")
        self.assertEqual(normalize_ai_model(None), "deepseek-v4-pro")

    def test_flash_request_uses_thinking_high_effort_and_non_streaming(self):
        completions = RecordingCompletions()
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

        create_deepseek_completion(client, "deepseek-v4-flash", "screen me")

        self.assertEqual(completions.kwargs["model"], "deepseek-v4-flash")
        self.assertEqual(completions.kwargs["reasoning_effort"], "high")
        self.assertEqual(
            completions.kwargs["extra_body"],
            {"thinking": {"type": "enabled"}},
        )
        self.assertIs(completions.kwargs["stream"], False)

    def test_pro_request_uses_selected_model(self):
        completions = RecordingCompletions()
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

        create_deepseek_completion(client, "deepseek-v4-pro", "screen me")

        self.assertEqual(completions.kwargs["model"], "deepseek-v4-pro")

    def test_connection_check_uses_low_token_non_thinking_deepseek_request(self):
        completions = RecordingCompletions()
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

        with patch("ai_models.OpenAI", return_value=client):
            result = check_ai_connection("secret", "deepseek-v4-flash")

        self.assertEqual(result["model"], "deepseek-v4-flash")
        self.assertGreaterEqual(result["latency_ms"], 0)
        self.assertEqual(completions.kwargs["model"], "deepseek-v4-flash")
        self.assertEqual(completions.kwargs["max_tokens"], 8)
        self.assertEqual(
            completions.kwargs["extra_body"],
            {"thinking": {"type": "disabled"}},
        )
        self.assertIs(completions.kwargs["stream"], False)

    def test_connection_check_uses_low_token_minimax_request(self):
        messages = RecordingMessages()
        client = SimpleNamespace(messages=messages)

        with patch("ai_models.anthropic.Anthropic", return_value=client):
            result = check_ai_connection("secret", "minimax")

        self.assertEqual(result["model"], "minimax")
        self.assertEqual(messages.kwargs["model"], "MiniMax-M2.1")
        self.assertEqual(messages.kwargs["max_tokens"], 8)

    def test_classifies_provider_and_transport_errors_safely(self):
        cases = [
            (ProviderStatusError(401), (401, "invalid_api_key")),
            (ProviderStatusError(402), (402, "insufficient_balance")),
            (ProviderStatusError(429), (429, "rate_limited")),
            (ProviderStatusError(400), (502, "provider_error")),
            (httpx.ConnectError("socket details"), (503, "network_error")),
            (httpx.TimeoutException("timeout details"), (503, "timeout")),
            (
                json.JSONDecodeError("bad response", "x", 0),
                (502, "invalid_response"),
            ),
        ]

        for error, expected in cases:
            with self.subTest(error=type(error).__name__):
                status, category, message = classify_ai_error(error)
                self.assertEqual((status, category), expected)
                self.assertNotIn("details", message.lower())


if __name__ == "__main__":
    unittest.main()
