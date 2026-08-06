import unittest
import uuid
from unittest.mock import patch

import httpx
import pandas as pd

import app


class ProviderStatusError(Exception):
    def __init__(self, status_code):
        super().__init__(f"provider status {status_code}")
        self.status_code = status_code


class AIConnectionEndpointTest(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def test_rejects_missing_api_key_without_provider_request(self):
        with patch("app.check_ai_connection") as check:
            response = self.client.post(
                "/test-ai-connection",
                json={"api_key": "", "ai_model": "deepseek-v4-pro"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "missing_api_key")
        check.assert_not_called()

    def test_normalizes_model_and_returns_connection_details(self):
        with patch(
            "app.check_ai_connection",
            return_value={"model": "deepseek-v4-pro", "latency_ms": 12},
        ) as check:
            response = self.client.post(
                "/test-ai-connection",
                json={"api_key": "secret", "ai_model": "invalid"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {
                "ok": True,
                "model": "deepseek-v4-pro",
                "latency_ms": 12,
            },
        )
        check.assert_called_once_with("secret", "deepseek-v4-pro")

    def test_returns_safe_categorized_provider_error(self):
        with patch(
            "app.check_ai_connection",
            side_effect=ProviderStatusError(401),
        ):
            response = self.client.post(
                "/test-ai-connection",
                json={"api_key": "bad-secret", "ai_model": "deepseek-v4-flash"},
            )

        payload = response.get_json()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(payload["error"], "invalid_api_key")
        self.assertNotIn("bad-secret", payload["message"])


class AIScreeningFailureTest(unittest.TestCase):
    def test_provider_connection_failure_marks_task_as_error(self):
        task_id = str(uuid.uuid4())
        app.tasks[task_id] = {
            "status": "queued",
            "progress": 0,
            "message": "Queued...",
            "result": None,
            "screening_log": [],
            "screening_log_count": 0,
        }
        papers = pd.DataFrame(
            [
                {
                    "Title": "Example paper",
                    "Abstract": "Example abstract",
                    "Source title": "Example journal",
                }
            ]
        )

        try:
            with patch("builtins.print"), patch(
                "app.create_deepseek_completion",
                side_effect=httpx.ConnectError("blocked socket details"),
            ):
                app.screen_literature_task(
                    task_id,
                    papers,
                    "",
                    "",
                    api_key="secret",
                    ai_criteria="Exclude this paper",
                    ai_model="deepseek-v4-pro",
                )

            self.assertEqual(app.tasks[task_id]["status"], "error")
            self.assertIn("network_error", app.tasks[task_id]["error"])
            self.assertNotIn("blocked socket details", app.tasks[task_id]["error"])
        finally:
            app.tasks.pop(task_id, None)


if __name__ == "__main__":
    unittest.main()
