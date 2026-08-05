# DeepSeek V4 Model Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the retired `deepseek-chat` integration with selectable DeepSeek V4 Pro and V4 Flash requests while preserving MiniMax-M2.1.

**Architecture:** Put DeepSeek model validation and Chat Completions request construction in a small `ai_models.py` boundary module. The Flask application normalizes the submitted model once, reuses that value for client setup and each screening request, and renders matching choices in the existing dropdown.

**Tech Stack:** Python 3, Flask, OpenAI-compatible Python SDK, `unittest`, HTML/JavaScript.

## Global Constraints

- Supported model identifiers are exactly `deepseek-v4-pro`, `deepseek-v4-flash`, and `minimax`.
- Missing, legacy, or unknown model values fall back to `deepseek-v4-pro`.
- DeepSeek requests use `https://api.deepseek.com`, thinking mode enabled, reasoning effort `high`, and `stream=False`.
- MiniMax-M2.1 behavior remains unchanged.
- Automated tests must not make a live DeepSeek request or require an API key.

---

### Task 1: DeepSeek request contract

**Files:**
- Create: `ai_models.py`
- Create: `tests/test_ai_models.py`

**Interfaces:**
- Produces: `DEFAULT_AI_MODEL: str`, `normalize_ai_model(value: str | None) -> str`, and `create_deepseek_completion(client, model: str, prompt: str)`.
- `create_deepseek_completion` returns the SDK response object unchanged.

- [ ] **Step 1: Write failing normalization and request-contract tests**

```python
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
        self.assertEqual(completions.kwargs["extra_body"], {"thinking": {"type": "enabled"}})
        self.assertIs(completions.kwargs["stream"], False)

    def test_pro_request_uses_selected_model(self):
        completions = RecordingCompletions()
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        create_deepseek_completion(client, "deepseek-v4-pro", "screen me")
        self.assertEqual(completions.kwargs["model"], "deepseek-v4-pro")
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python -m unittest tests.test_ai_models -v`

Expected: import failure because `ai_models.py` does not exist.

- [ ] **Step 3: Implement the minimal request boundary**

```python
DEFAULT_AI_MODEL = "deepseek-v4-pro"
SUPPORTED_AI_MODELS = {DEFAULT_AI_MODEL, "deepseek-v4-flash", "minimax"}


def normalize_ai_model(value):
    return value if value in SUPPORTED_AI_MODELS else DEFAULT_AI_MODEL


def create_deepseek_completion(client, model, prompt):
    return client.chat.completions.create(
        model=normalize_ai_model(model),
        messages=[
            {"role": "system", "content": "You are a paper screening assistant. Output ONLY valid JSON: {\"exclude\": true/false, \"reason\": \"text\"}. Be concise."},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}},
        stream=False,
    )
```

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run: `python -m unittest tests.test_ai_models -v`

Expected: three tests pass.

### Task 2: Flask and UI integration

**Files:**
- Modify: `app.py`
- Modify: `templates/index.html`
- Create: `tests/test_deepseek_v4_integration.py`

**Interfaces:**
- Consumes: `DEFAULT_AI_MODEL`, `normalize_ai_model`, and `create_deepseek_completion` from Task 1.
- Produces: a model dropdown whose submitted values match the backend model identifiers.

- [ ] **Step 1: Write a failing Flask/UI integration test**

```python
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

    def test_screen_normalizes_unknown_model_before_starting_worker(self):
        with patch("app.threading.Thread") as thread:
            response = app.app.test_client().post(
                "/screen",
                data={"file": (io.BytesIO(b"Title,Abstract\nA,B\n"), "papers.csv"), "ai_model": "invalid"},
                content_type="multipart/form-data",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(thread.call_args.kwargs["kwargs"]["ai_model"], "deepseek-v4-pro")
```

- [ ] **Step 2: Run the integration tests and verify RED**

Run: `python -m unittest tests.test_deepseek_v4_integration -v`

Expected: missing dropdown values and unnormalized worker argument.

- [ ] **Step 3: Wire normalized selection into Flask and DeepSeek calls**

Import Task 1 helpers. Default and normalize the form field, default the worker to `deepseek-v4-pro`, use the selected identifier as `model_name`, and replace the inline DeepSeek SDK call with `create_deepseek_completion(client, ai_model, prompt)`.

- [ ] **Step 4: Add the two dropdown choices and translations**

Replace the generic DeepSeek option with `deepseek-v4-pro` and `deepseek-v4-flash`, add English/Chinese labels, and make both values select the existing DeepSeek icon.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run: `python -m unittest tests.test_ai_models tests.test_deepseek_v4_integration -v`

Expected: all focused tests pass.

### Task 3: Documentation and full verification

**Files:**
- Modify: `README.md`
- Modify: `docs/AI_MODEL_GUIDE.md`

**Interfaces:**
- Consumes: the final model names and request behavior from Tasks 1-2.
- Produces: user-facing setup and selection instructions for both DeepSeek V4 variants.

- [ ] **Step 1: Update model documentation**

Document both model choices, their shared API base URL and API key, thinking mode, high reasoning effort, and the Pro-versus-Flash speed/cost trade-off without changing unrelated release notes.

- [ ] **Step 2: Run the complete automated test suite**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`

Expected: all discovered tests pass with zero failures.

- [ ] **Step 3: Verify syntax and whitespace**

Run: `python -m py_compile app.py ai_models.py tests/test_ai_models.py tests/test_deepseek_v4_integration.py`

Run: `git diff --check`

Expected: both commands exit successfully.

- [ ] **Step 4: Review and publish**

Inspect `git diff --stat`, `git diff`, and `git status --short`; commit the verified implementation, push `main` to `origin`, and confirm the remote branch contains the new commit.
