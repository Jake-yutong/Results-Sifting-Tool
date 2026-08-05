# DeepSeek V4 Model Selection Design

## Goal

Upgrade the existing DeepSeek integration from `deepseek-chat` to `deepseek-v4-pro` and add `deepseek-v4-flash` as a selectable alternative, while preserving MiniMax-M2.1 support.

## Selected approach

Use explicit application-level model identifiers for all three UI choices:

- `deepseek-v4-pro`
- `deepseek-v4-flash`
- `minimax`

The selected DeepSeek identifier is passed through unchanged to the DeepSeek Chat Completions API. This keeps UI state, form submission, logging, and the API payload aligned and avoids a second mapping layer.

Two alternatives were considered but rejected:

- Keeping the generic `deepseek` identifier and adding a separate variant field would add unnecessary state and validation.
- Sending raw HTTP requests would duplicate connection, timeout, and retry behavior already provided by the OpenAI-compatible client.

## Request behavior

Both DeepSeek V4 options use the existing `https://api.deepseek.com` base URL and send:

- the selected model name;
- the existing system and user messages;
- `thinking: {"type": "enabled"}`;
- `reasoning_effort: "high"`;
- non-streaming behavior;
- the existing JSON response requirement used by literature screening.

Provider-specific fields are supplied through the OpenAI client's extra request body mechanism so the integration remains compatible with the OpenAI-style SDK used by the project.

The server accepts only the three known model identifiers. Missing or unknown values fall back to `deepseek-v4-pro` for backward compatibility and to prevent arbitrary model names from reaching the provider.

## User interface

The model dropdown displays DeepSeek V4 Pro, DeepSeek V4 Flash, and MiniMax-M2.1. Both DeepSeek choices reuse the existing DeepSeek icon. English and Chinese translation dictionaries receive labels for the two V4 choices.

## Error handling

The current timeout, retry, JSON parsing, and per-paper error handling remain in place. Logs include the concrete DeepSeek model name so users can confirm which option is active.

## Testing

Automated tests will verify:

- model selection normalization and fallback behavior;
- the DeepSeek request arguments for both Pro and Flash, including thinking mode, reasoning effort, and non-streaming mode;
- the rendered page exposes both DeepSeek choices and posts the selected value;
- the existing test suite and application import/build checks remain successful.

No live API request will be made during automated tests because it would require a secret and incur external usage. The request contract will be tested at the client boundary.
