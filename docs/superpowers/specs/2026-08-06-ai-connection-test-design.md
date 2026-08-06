# AI Connection Test and Reliable Failure Design

## Goal

Add a low-token **Test API Connection** action for the currently selected AI model and prevent failed AI requests from being reported as successful screening.

## Root cause

The screening worker currently catches every per-paper AI exception, logs it only to the server console, and continues. If every request fails, no rows are excluded and the task is still marked `completed`. This makes network, authentication, model, quota, and response-format failures look like ignored screening criteria.

The process currently launched from the restricted development shell also cannot open outbound sockets. A direct request fails with Windows socket error 10013, while the same request from an unrestricted process reaches DeepSeek and returns the expected unauthenticated response. The application must expose this distinction to the user.

## API connection endpoint

Add `POST /test-ai-connection`. It accepts JSON containing `api_key` and `ai_model`, normalizes the model through the existing allow-list, and rejects an empty key before contacting a provider.

For DeepSeek V4 Pro and Flash, the endpoint uses the existing OpenAI-compatible client and sends a non-streaming request with:

- the selected model;
- a prompt requesting only `OK`;
- thinking mode disabled;
- `max_tokens=8`.

This validates network access, the API key, the selected model, and the Chat Completions endpoint while minimizing billable output. It does not store, log, or return the API key.

For MiniMax-M2.1, the endpoint performs the equivalent minimal Anthropic-compatible message request with `max_tokens=8`.

Successful responses return `ok`, the normalized model name, and elapsed milliseconds. Failures return a safe user-facing category and message:

- missing API key: HTTP 400;
- invalid API key: HTTP 401;
- insufficient balance: HTTP 402;
- rate limit: HTTP 429;
- network or timeout failure: HTTP 503;
- other provider rejection: HTTP 502.

Provider exception text is not returned verbatim when it could expose request details.

## User interface

Place a secondary **Test API Connection** button directly below the API key input. Clicking it sends the selected model and key to the connection endpoint without uploading a literature file.

While testing, the button is disabled and displays a testing state. The result appears below it:

- green: connection succeeded, including model and latency;
- red: concise categorized failure guidance.

English and Chinese translations cover the button, in-progress state, success state, and validation errors.

## Screening failure behavior

Formal AI screening must not silently keep an unscreened paper. After the existing retry policy is exhausted, the worker raises a categorized error, stops the task, and exposes the error through the existing task-status `error` state. The UI already renders that state as an error message.

Keyword-only screening remains unchanged when no API key or AI criteria is provided.

## Testing

Automated tests use fake provider clients and Flask's test client; no live API key or billable request is required. Tests cover:

- the exact low-token DeepSeek request contract;
- successful connection endpoint response;
- missing key, authentication, rate-limit, network, and provider errors;
- model normalization;
- rendered connection-test controls;
- failed formal AI calls producing task error instead of successful zero-exclusion output;
- the existing model-selection and RTF tests.
