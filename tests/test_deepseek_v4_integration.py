import io
import unittest
from unittest.mock import patch

import app


class DeepSeekV4IntegrationTest(unittest.TestCase):
    def test_index_exposes_pro_and_flash_model_choices(self):
        response = app.app.test_client().get("/")

        html = response.get_data(as_text=True)

        self.assertIn('value="deepseek-v4-pro"', html)
        self.assertIn('value="deepseek-v4-flash"', html)

    def test_index_exposes_api_connection_test_controls(self):
        response = app.app.test_client().get("/")

        html = response.get_data(as_text=True)

        self.assertIn('id="testApiBtn"', html)
        self.assertIn('id="apiTestStatus"', html)
        self.assertIn("fetch('/test-ai-connection'", html)
        self.assertEqual(html.count("'btn-test-api':"), 2)
        self.assertEqual(html.count("'status-api-testing':"), 2)

    def test_screen_normalizes_unknown_model_before_starting_worker(self):
        with patch("app.threading.Thread") as thread:
            response = app.app.test_client().post(
                "/screen",
                data={
                    "file": (
                        io.BytesIO(
                            b"Title,Abstract,Source title\n"
                            b"Example,Test abstract,Test journal\n"
                        ),
                        "papers.csv",
                    ),
                    "ai_model": "invalid",
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            thread.call_args.kwargs["kwargs"]["ai_model"],
            "deepseek-v4-pro",
        )


if __name__ == "__main__":
    unittest.main()
