import io
import unittest
from unittest.mock import patch

import app


class FileUploadLoggingFailureTest(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def _post_csv(self, content):
        return self.client.post(
            "/screen",
            data={
                "file": (
                    io.BytesIO(content),
                    "cleaned_data_20260805_160000.csv",
                ),
                "ai_model": "deepseek-v4-flash",
                "api_key": "",
                "ai_criteria": "",
                "ta_keywords": "",
                "journal_keywords": "",
                "remove_duplicates": "false",
            },
            content_type="multipart/form-data",
        )

    def test_exported_csv_is_accepted_when_console_output_is_invalid(self):
        content = (
            b"Title,Abstract,Source title\n"
            b"Example paper,Example abstract,Example journal\n"
        )

        with patch(
            "builtins.print",
            side_effect=OSError(22, "Invalid argument"),
        ), patch("app.threading.Thread") as thread_class:
            response = self._post_csv(content)

        payload = response.get_json()
        task_id = payload.get("task_id")
        try:
            self.assertEqual(response.status_code, 200)
            self.assertIsNotNone(task_id)
            thread_class.return_value.start.assert_called_once_with()
        finally:
            if task_id:
                app.tasks.pop(task_id, None)

    def test_malformed_csv_remains_a_parse_error_when_console_is_invalid(self):
        with patch(
            "builtins.print",
            side_effect=OSError(22, "Invalid argument"),
        ):
            response = self._post_csv(b"not a tabular export")

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("Errno 22", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
