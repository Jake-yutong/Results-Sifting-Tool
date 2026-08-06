# AI Connection Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a low-token API connection test and stop formal screening from reporting success when AI requests fail.

**Architecture:** Extend `ai_models.py` with provider connection checks and safe exception classification. Expose those capabilities through one Flask JSON endpoint, add a small status-driven UI control, and reuse the same error classifier in the screening worker's fail-fast path.

**Tech Stack:** Python 3, Flask, OpenAI SDK, Anthropic SDK, httpx, JavaScript, `unittest`.

## Global Constraints

- Connection tests must never log, store, or return API keys.
- DeepSeek connection tests use the selected V4 model, `thinking.type=disabled`, `max_tokens=8`, and `stream=False`.
- MiniMax connection tests use MiniMax-M2.1 with `max_tokens=8`.
- No automated test makes a live provider request.
- Formal AI screening must end in task status `error` after provider retries are exhausted.
- Keyword-only screening behavior remains unchanged.

---

### Task 1: Provider connection contract and error classification

**Files:**
- Modify: `ai_models.py`
- Modify: `tests/test_ai_models.py`

**Interfaces:**
- Produces: `check_ai_connection(api_key: str, model: str) -> dict` with `model` and `latency_ms`.
- Produces: `classify_ai_error(error: Exception) -> tuple[int, str, str]` containing HTTP status, stable category, and safe message.

- [ ] **Step 1: Write failing request-contract and classifier tests**

Add tests asserting that DeepSeek uses the normalized model, `max_tokens=8`, disabled thinking, and non-streaming mode; that MiniMax uses `MiniMax-M2.1` and `max_tokens=8`; and that authentication, balance, rate-limit, connection/timeout, invalid JSON, and generic provider errors map to safe categories.

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv\Scripts\python.exe -m unittest tests.test_ai_models -v`

Expected: imports fail because the new interfaces do not exist.

- [ ] **Step 3: Implement minimal provider checks and classifier**

Use SDK clients with existing provider base URLs, `time.perf_counter()` for latency, and explicit exception-type/status-code checks. Return fixed safe messages rather than raw provider request details.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `.venv\Scripts\python.exe -m unittest tests.test_ai_models -v`

Expected: all model tests pass.

### Task 2: Flask endpoint and fail-fast screening

**Files:**
- Modify: `app.py`
- Create: `tests/test_ai_connection.py`

**Interfaces:**
- Consumes: `check_ai_connection` and `classify_ai_error` from Task 1.
- Produces: `POST /test-ai-connection` accepting `{api_key, ai_model}`.

- [ ] **Step 1: Write failing endpoint tests**

Cover missing keys, normalized models, success payloads, and categorized failures by patching only the external connection boundary.

- [ ] **Step 2: Write a failing screening regression test**

Run `screen_literature_task` with one candidate and a patched provider call that raises `httpx.ConnectError`; assert task status is `error`, its message is categorized, and it is not marked `completed`.

- [ ] **Step 3: Run tests and verify RED**

Run: `.venv\Scripts\python.exe -m unittest tests.test_ai_connection -v`

Expected: missing route and existing silent-success behavior fail assertions.

- [ ] **Step 4: Implement the endpoint and fail-fast error propagation**

Validate JSON input, call the provider boundary, return safe categorized errors, and replace the screening worker's `continue`/outer swallow behavior with a raised categorized error after retries.

- [ ] **Step 5: Run focused backend tests and verify GREEN**

Run: `.venv\Scripts\python.exe -m unittest tests.test_ai_models tests.test_ai_connection -v`

Expected: all focused backend tests pass.

### Task 3: Connection-test user interface

**Files:**
- Modify: `templates/index.html`
- Modify: `tests/test_deepseek_v4_integration.py`

**Interfaces:**
- Consumes: `POST /test-ai-connection`.
- Produces: `#testApiBtn` and `#apiTestStatus` with translated testing, success, and failure states.

- [ ] **Step 1: Write a failing rendered-interface test**

Assert the index page contains the connection button, result status region, endpoint fetch, and both translation keys.

- [ ] **Step 2: Run the interface test and verify RED**

Run: `.venv\Scripts\python.exe -m unittest tests.test_deepseek_v4_integration -v`

Expected: required controls are absent.

- [ ] **Step 3: Implement button styling, markup, translations, and fetch behavior**

Disable the button during the request, reject an empty key locally, submit only the selected model and key, and render green/red status text without echoing the key.

- [ ] **Step 4: Run focused interface tests and verify GREEN**

Run: `.venv\Scripts\python.exe -m unittest tests.test_deepseek_v4_integration -v`

Expected: all interface tests pass.

### Task 4: Full verification and runtime handoff

**Files:**
- Modify: `README.md`
- Modify: `docs/AI_MODEL_GUIDE.md`

**Interfaces:**
- Documents the connection check, token cap, and failure behavior.

- [ ] **Step 1: Update user documentation**

Explain how to run the connection test before screening and how to interpret categorized errors.

- [ ] **Step 2: Run complete verification**

Run: `.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v`

Run: `.venv\Scripts\python.exe -m py_compile app.py ai_models.py tests\test_ai_models.py tests\test_ai_connection.py tests\test_deepseek_v4_integration.py`

Run: `git diff --check`

Expected: every command exits successfully.

- [ ] **Step 3: Restart with outbound network access**

Stop the restricted development-server process, start the verified app in an approved unrestricted process, confirm HTTP 200 locally, and leave the page ready for the user to test with their own key.

- [ ] **Step 4: Review and commit**

Inspect the complete diff and commit the verified feature. Do not push unless the user separately authorizes a GitHub update for this change.
