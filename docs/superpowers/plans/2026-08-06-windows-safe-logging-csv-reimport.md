# Windows Safe Logging CSV Reimport Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure a Windows background process with an invalid stdout handle can still reimport the tool's exported CSV and create a screening task.

**Architecture:** Add one module-level `safe_print` boundary in `app.py` that delegates to `builtins.print` and absorbs only `OSError` and `ValueError` from unusable console streams. Existing module diagnostics resolve through that boundary, while CSV parsing, task creation, and all non-logging exceptions retain their current behavior.

**Tech Stack:** Python 3, Flask test client, pandas, unittest, unittest.mock.

## Global Constraints

- Do not change CSV auto-detection, field mapping, export format, filenames, screening behavior, or DeepSeek API behavior.
- Catch only `OSError` and `ValueError` at the logging boundary.
- Do not add sensitive data to logs.
- Verify the tool's own exported CSV shape can be uploaded through the real `/screen` route.

---

## File Structure

- Modify `app.py`: define the safe module-level console output boundary used by all existing diagnostic `print` calls.
- Create `tests/test_file_upload.py`: exercise `/screen` with an exported-format CSV and a broken console stream, plus a malformed-file control case.
- Update `README.md`: briefly note that downloaded CSV files are valid inputs for subsequent screening runs.

### Task 1: Reproduce stdout failure in the upload route

**Files:**
- Create: `tests/test_file_upload.py`
- Test: `tests/test_file_upload.py`

**Interfaces:**
- Consumes: Flask application `app.app`, task store `app.tasks`, and route `POST /screen`.
- Produces: regression tests for the code-level `safe_print(*args, **kwargs) -> None` boundary added in Task 2.

- [ ] **Step 1: Write the failing exported-CSV regression test**

```python
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
```

- [ ] **Step 2: Write the malformed-file control test**

```python
    def test_malformed_csv_remains_a_parse_error_when_console_is_invalid(self):
        with patch(
            "builtins.print",
            side_effect=OSError(22, "Invalid argument"),
        ):
            response = self._post_csv(b"not a tabular export")

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("Errno 22", response.get_json()["error"])
```

- [ ] **Step 3: Run the focused tests and verify RED**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_file_upload -v
```

Expected: both tests fail because the existing raw `print(..., flush=True)` raises `OSError(22)` and becomes the route error.

- [ ] **Step 4: Commit the failing regression tests**

```powershell
git add tests/test_file_upload.py
git commit -m "test: reproduce CSV reimport logging failure"
```

### Task 2: Isolate console logging failures from business logic

**Files:**
- Modify: `app.py:10-35`
- Test: `tests/test_file_upload.py`

**Interfaces:**
- Consumes: `builtins.print(*args, **kwargs)`.
- Produces: `safe_print(*args, **kwargs) -> None` and module alias `print = safe_print` for all diagnostics in `app.py`.

- [ ] **Step 1: Add the minimal safe logging boundary**

Add `import builtins` beside the standard-library imports, then define the boundary before the first application diagnostic can run:

```python
def safe_print(*args, **kwargs):
    """Write diagnostics without allowing a broken console to fail work."""
    try:
        builtins.print(*args, **kwargs)
    except (OSError, ValueError):
        return


print = safe_print
```

No other exceptions are caught. Existing `print` call sites remain unchanged and resolve to the module alias.

- [ ] **Step 2: Run focused tests and verify GREEN**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_file_upload -v
```

Expected: 2 tests pass; the exported-format CSV returns a task ID and the malformed file still returns HTTP 400 without `Errno 22`.

- [ ] **Step 3: Run the existing AI connection regression tests**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_ai_connection tests.test_ai_models tests.test_deepseek_v4_integration -v
```

Expected: all existing API tests pass without behavior changes.

- [ ] **Step 4: Commit the production fix**

```powershell
git add app.py
git commit -m "fix: isolate console failures from CSV uploads"
```

### Task 3: Document and verify round-trip support

**Files:**
- Modify: `README.md`
- Test: all files under `tests/`

**Interfaces:**
- Consumes: completed upload fix from Task 2.
- Produces: user-visible assurance that `cleaned_data_*.csv` can be reused as input.

- [ ] **Step 1: Add the README note**

Under the existing file-format or usage guidance, add:

```markdown
Files downloaded as `cleaned_data_*.csv` can be uploaded again for a subsequent screening run.
```

- [ ] **Step 2: Run the complete automated verification**

Run:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
.venv\Scripts\python.exe -m py_compile app.py ai_models.py tests\test_file_upload.py
git diff --check
```

Expected: all tests pass, compilation succeeds, and `git diff --check` reports no errors.

- [ ] **Step 3: Commit documentation**

```powershell
git add README.md
git commit -m "docs: document CSV round-trip uploads"
```

### Task 4: Restart and verify the real HTTP boundary

**Files:**
- No repository file changes.

**Interfaces:**
- Consumes: local Flask server at `http://127.0.0.1:5000/`.
- Produces: runtime evidence that the browser-facing process accepts exported CSV content.

- [ ] **Step 1: Stop the existing Flask process and restart with native Windows stdout/stderr redirection**

Start `.venv\Scripts\python.exe -X utf8 app.py` in a hidden process with separate output and error log files.

- [ ] **Step 2: Upload exported-format CSV through HTTP**

POST an in-memory multipart file named `cleaned_data_20260805_160000.csv` with `Title`, `Abstract`, and `Source title` columns to `/screen`.

Expected: HTTP 200 with a `task_id`, never HTTP 400 with `[Errno 22]`.

- [ ] **Step 3: Poll the task status**

GET `/status/<task_id>` until completion.

Expected: `status` becomes `completed` for the no-AI, one-row input.

- [ ] **Step 4: Confirm repository state and push**

```powershell
git status -sb
git push origin main
git ls-remote origin refs/heads/main
```

Expected: the local and remote `main` hashes match and the working tree is clean.
