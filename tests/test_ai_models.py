import unittest
from types import SimpleNamespace

from ai_models import create_deepseek_completion, normalize_ai_model


class RecordingCompletions:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(choices=[])


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


if __name__ == "__main__":
    unittest.main()
