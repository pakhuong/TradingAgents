---
title: OpenRouter Reasoning Support for TradingAgents
version: 1.0
date_created: 2026-05-06
last_updated: 2026-05-06
owner: TradingAgents maintainers
tags: [design, llm, openrouter, reasoning, config]
---

# Introduction

This specification defines how TradingAgents shall add explicit OpenRouter reasoning support while preserving the existing native OpenAI, Google, Anthropic, Ollama, and other OpenAI-compatible provider behavior. The goal is to let users choose an OpenRouter reasoning effort level through TradingAgents configuration and CLI flows, then translate that semantic setting into the OpenRouter request shape expected by the OpenRouter Chat Completions API.

## 1. Purpose & Scope

This specification applies to the TradingAgents Python repository and the current OpenAI-compatible provider path implemented through `tradingagents/llm_clients/openai_client.py`.

The scope includes:

- Adding a dedicated OpenRouter reasoning configuration key.
- Adding CLI selection flow for OpenRouter reasoning effort.
- Passing the reasoning configuration through the graph-level provider kwargs path.
- Translating OpenRouter reasoning configuration into the OpenRouter request body shape.
- Preserving existing native OpenAI reasoning support and Responses API behavior.
- Adding focused tests for config plumbing and client request-shape translation.
- Updating user-facing documentation where reasoning behavior is described.

The scope excludes:

- Preserving or displaying returned reasoning tokens, `reasoning`, or `reasoning_details` in TradingAgents outputs.
- Adding OpenRouter-specific support for `reasoning.max_tokens`, `reasoning.exclude`, or `reasoning.enabled` in the first implementation pass.
- Adding model-by-model reasoning capability validation for OpenRouter.
- Refactoring the broader LLM client factory or agent orchestration design.
- Streaming-specific reasoning token handling.

## 2. Definitions

- **TradingAgents**: The multi-agent trading research framework in this repository.
- **OpenRouter**: A third-party inference router that exposes an OpenAI-compatible Chat Completions API and a unified `reasoning` request object across multiple model providers.
- **Native OpenAI provider**: The `llm_provider == "openai"` path in TradingAgents, which uses the OpenAI Responses API and top-level `reasoning_effort`.
- **OpenRouter provider**: The `llm_provider == "openrouter"` path in TradingAgents, which uses OpenRouter's OpenAI-compatible Chat Completions endpoint at `https://openrouter.ai/api/v1`.
- **Reasoning effort**: A symbolic configuration value that adjusts how much reasoning budget a reasoning-capable model uses before producing its final answer.
- **Semantic provider kwargs**: Provider-related settings expressed in TradingAgents terms before any provider-specific wire-format translation is applied.
- **Wire-format translation**: The provider-specific conversion from TradingAgents semantic settings into the exact request payload expected by the upstream API.
- **`extra_body`**: The LangChain/OpenAI SDK parameter used to pass provider-specific JSON fields that do not belong to the standard top-level OpenAI Chat Completions schema.
- **Chat Completions**: The OpenAI-compatible `/chat/completions` request shape used by OpenRouter and other third-party compatible providers in this repository.
- **Responses API**: OpenAI's native `/responses` API used only for `llm_provider == "openai"` in this repository.

## 3. Requirements, Constraints & Guidelines

### Functional Requirements

- **REQ-001**: Add a new configuration key named `openrouter_reasoning_effort` to `tradingagents/default_config.py` with a default value of `None`.
- **REQ-002**: The interactive CLI shall prompt for OpenRouter reasoning effort when the selected LLM provider is `openrouter`.
- **REQ-003**: The CLI selection result shall be persisted into the runtime config under `openrouter_reasoning_effort`.
- **REQ-004**: `TradingAgentsGraph._get_provider_kwargs()` shall read `openrouter_reasoning_effort` when `llm_provider == "openrouter"`.
- **REQ-005**: `TradingAgentsGraph._get_provider_kwargs()` shall pass the OpenRouter reasoning selection forward as a semantic reasoning setting instead of directly encoding OpenRouter wire-format details in the graph layer.
- **REQ-006**: `OpenAIClient.get_llm()` shall translate the OpenRouter semantic reasoning setting into `extra_body={"reasoning": {"effort": <value>}}` when `provider == "openrouter"`.
- **REQ-007**: For the OpenRouter provider, the client shall not forward the same reasoning selection as a top-level `reasoning_effort` field after translation.
- **REQ-008**: When `extra_body` is already present in client kwargs, the OpenRouter reasoning translation shall merge into the existing mapping instead of replacing it.
- **REQ-009**: When `extra_body["reasoning"]` already exists and is a mapping, the translated `effort` value shall be merged into that mapping while preserving unrelated keys.
- **REQ-010**: When `openrouter_reasoning_effort` is `None` or absent, TradingAgents shall not add a `reasoning` object to OpenRouter requests.
- **REQ-011**: Native OpenAI behavior shall remain unchanged: `llm_provider == "openai"` shall continue to use `use_responses_api = True` and top-level `reasoning_effort`.
- **REQ-012**: OpenRouter shall continue to use Chat Completions and shall not opt into the OpenAI Responses API path.
- **REQ-013**: The implementation shall preserve structured-output and tool-calling compatibility for OpenRouter runs.
- **REQ-014**: The implementation shall add focused unit tests for graph config plumbing, client translation, and `extra_body` merge behavior.
- **REQ-015**: Documentation shall explain that OpenRouter reasoning support is configured separately from native OpenAI reasoning support.

### Compatibility Requirements

- **CMP-001**: Existing Google thinking-level behavior shall remain unchanged.
- **CMP-002**: Existing Anthropic effort behavior shall remain unchanged.
- **CMP-003**: Existing native OpenAI reasoning behavior shall remain unchanged.
- **CMP-004**: Existing OpenRouter model validation behavior shall remain unchanged. Custom OpenRouter model IDs shall remain accepted.
- **CMP-005**: Existing Ollama and other OpenAI-compatible provider behavior shall remain unchanged.
- **CMP-006**: The default test suite shall not require live OpenRouter credentials or network access.

### Constraints

- **CON-001**: Do not overload `openai_reasoning_effort` to also represent OpenRouter reasoning. OpenRouter shall use its own config key.
- **CON-002**: Do not hardcode OpenRouter request-body details inside CLI code or graph orchestration code.
- **CON-003**: Do not enable `use_responses_api` for OpenRouter.
- **CON-004**: Do not add persistent storage, logging, or display of returned reasoning tokens in the first pass.
- **CON-005**: Do not add model allowlist validation for whether a specific OpenRouter model supports reasoning. OpenRouter model catalogs change frequently and custom IDs are already allowed.
- **CON-006**: Do not add real API calls to the automated test suite.
- **CON-007**: Do not break existing `extra_body` usage by overwriting unrelated keys.
- **CON-008**: Do not add support for OpenRouter `reasoning.max_tokens`, `reasoning.exclude`, or `reasoning.enabled` in the first pass unless the user explicitly expands scope later.

### Guidelines

- **GUD-001**: Keep OpenRouter wire-format translation localized to `tradingagents/llm_clients/openai_client.py`, because that file already owns provider-specific base URLs and provider-specific request-shape behavior for OpenAI-compatible providers.
- **GUD-002**: Keep the graph layer provider-agnostic at the semantic-setting level. The graph should know that OpenRouter has a reasoning-effort concept, but it should not know the exact HTTP request nesting.
- **GUD-003**: Prefer a small helper function for `extra_body` merging over ad hoc inline dict mutation.
- **GUD-004**: Preserve existing CLI style and terminology, but label the OpenRouter prompt clearly enough that users understand it is separate from native OpenAI reasoning effort.
- **GUD-005**: Use OpenRouter's documented `reasoning.effort` values for interactive selections.
- **PAT-001**: Follow the existing repository pattern of provider-specific config key -> graph provider kwargs -> client translation -> SDK constructor kwargs.

## 4. Interfaces & Data Contracts

### 4.1 Configuration Contract

`tradingagents/default_config.py` shall define a new OpenRouter-specific key.

Required shape:

```python
DEFAULT_CONFIG = {
    # existing keys...
    "google_thinking_level": None,
    "openai_reasoning_effort": None,
    "openrouter_reasoning_effort": None,
    "anthropic_effort": None,
}
```

Supported values for `openrouter_reasoning_effort` in the first pass:

- `"xhigh"`
- `"high"`
- `"medium"`
- `"low"`
- `"minimal"`
- `"none"`
- `None`

Programmatic callers may set any non-empty string, but the CLI shall constrain interactive choices to the documented values above. TradingAgents shall not add hard validation beyond the interactive selector in the first pass.

Example:

```python
config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openrouter"
config["quick_think_llm"] = "openai/gpt-5-mini"
config["deep_think_llm"] = "openai/gpt-5"
config["openrouter_reasoning_effort"] = "high"
```

### 4.2 CLI Contract

The CLI selection flow shall add an OpenRouter branch during Step 8 provider-specific thinking configuration.

Recommended helper:

```python
def ask_openrouter_reasoning_effort() -> str | None:
    """Ask for OpenRouter reasoning effort level."""
```

Recommended interactive choices:

- `Medium (Default)` -> `"medium"`
- `High (More thorough)` -> `"high"`
- `Low (Faster)` -> `"low"`
- `Minimal (Lowest reasoning budget)` -> `"minimal"`
- `XHigh (Maximum reasoning budget)` -> `"xhigh"`
- `None (Disable reasoning)` -> `"none"`

The selections contract returned by `get_user_selections()` shall include:

```python
{
    # existing keys...
    "openrouter_reasoning_effort": "high",
}
```

`run_analysis()` shall copy that value into the runtime config exactly once:

```python
config["openrouter_reasoning_effort"] = selections.get("openrouter_reasoning_effort")
```

### 4.3 Graph Provider Kwargs Contract

`TradingAgentsGraph._get_provider_kwargs()` shall continue returning semantic provider kwargs.

Required behavior:

```python
elif provider == "openrouter":
    reasoning_effort = self.config.get("openrouter_reasoning_effort")
    if reasoning_effort:
        kwargs["reasoning_effort"] = reasoning_effort
```

Rules:

- The graph shall not emit `extra_body` solely to satisfy OpenRouter reasoning support.
- The graph shall preserve existing timeout handling.
- The graph shall preserve native OpenAI's current `reasoning_effort` path.

### 4.4 OpenRouter Client Translation Contract

`tradingagents/llm_clients/openai_client.py` shall translate semantic reasoning configuration into the OpenRouter wire format.

Required translation behavior:

```python
def _apply_openrouter_reasoning(llm_kwargs: dict, client_kwargs: dict) -> None:
    effort = client_kwargs.get("reasoning_effort")
    if not effort:
        return

    llm_kwargs.pop("reasoning_effort", None)

    extra_body = dict(llm_kwargs.get("extra_body") or {})
    reasoning = dict(extra_body.get("reasoning") or {})
    reasoning["effort"] = effort
    extra_body["reasoning"] = reasoning
    llm_kwargs["extra_body"] = extra_body
```

Rules:

- Apply this translation only when `provider == "openrouter"`.
- Apply the translation after generic passthrough kwargs are collected and before constructing `NormalizedChatOpenAI`.
- Preserve unrelated `extra_body` keys such as future provider-specific settings or debugging fields.
- Preserve existing nested `extra_body["reasoning"]` keys when that value is already a mapping.
- If `extra_body["reasoning"]` exists but is not a mapping, raise a clear `ValueError` rather than silently corrupting the payload.
- Do not set `use_responses_api` for OpenRouter.

Expected `NormalizedChatOpenAI` constructor kwargs for OpenRouter with reasoning enabled:

```python
{
    "model": "openai/gpt-5",
    "base_url": "https://openrouter.ai/api/v1",
    "api_key": "...",
    "timeout": 30,
    "extra_body": {
        "reasoning": {
            "effort": "high",
        }
    },
}
```

Expected merge behavior with existing `extra_body`:

```python
{
    "extra_body": {
        "provider": {"allow_fallbacks": True},
        "reasoning": {
            "exclude": True,
            "effort": "high",
        },
    }
}
```

### 4.5 Files To Modify

Required implementation files:

- `tradingagents/default_config.py`
- `cli/main.py`
- `cli/utils.py`
- `tradingagents/graph/trading_graph.py`
- `tradingagents/llm_clients/openai_client.py`
- `tests/test_graph_provider_kwargs.py`
- `tests/test_openai_client.py`

Recommended new test file:

- `tests/test_provider_reasoning_config.py`

Recommended documentation targets:

- `docs/user-guide.md`
- `README.md`

## 5. Acceptance Criteria

- **AC-001**: Given `llm_provider == "openrouter"` and `openrouter_reasoning_effort == "high"`, when `TradingAgentsGraph._get_provider_kwargs()` runs, then it returns `{"reasoning_effort": "high"}` plus any existing timeout value.
- **AC-002**: Given `llm_provider == "openrouter"` and `openrouter_reasoning_effort` is unset, when `TradingAgentsGraph._get_provider_kwargs()` runs, then it does not add a reasoning setting.
- **AC-003**: Given an OpenRouter client receives semantic `reasoning_effort == "high"` and no prior `extra_body`, when `get_llm()` runs, then the constructor kwargs include `extra_body["reasoning"]["effort"] == "high"` and do not include top-level `reasoning_effort`.
- **AC-004**: Given an OpenRouter client receives semantic `reasoning_effort == "high"` and existing `extra_body == {"provider": {"allow_fallbacks": True}}`, when `get_llm()` runs, then both the original `provider` block and the new `reasoning.effort` block are present.
- **AC-005**: Given an OpenRouter client receives semantic `reasoning_effort == "high"` and existing `extra_body == {"reasoning": {"exclude": True}}`, when `get_llm()` runs, then the final `extra_body["reasoning"]` contains both `exclude == True` and `effort == "high"`.
- **AC-006**: Given an OpenRouter client receives semantic `reasoning_effort == "high"` and existing `extra_body == {"reasoning": "bad-shape"}`, when `get_llm()` runs, then it raises a clear `ValueError`.
- **AC-007**: Given `llm_provider == "openai"` and `openai_reasoning_effort == "low"`, when `get_llm()` runs, then `use_responses_api == True` remains enabled and the native OpenAI path is unchanged.
- **AC-008**: Given the user selects OpenRouter in the CLI, when Step 8 runs, then the CLI asks for OpenRouter reasoning effort and stores the answer under `openrouter_reasoning_effort`.
- **AC-009**: Given the automated tests run in CI without API keys, then the new reasoning-support tests pass without network access.

## 6. Test Automation Strategy

- **Test Levels**: Unit tests only for the first pass.
- **Frameworks**: Pytest with `unittest.mock.patch` or pytest monkeypatch.
- **Primary Test Surface**:
  - Graph config plumbing.
  - OpenRouter client translation to `extra_body`.
  - Merge behavior with existing `extra_body`.
  - Preservation of native OpenAI behavior.
  - CLI selection-to-config plumbing where feasible without interactive terminal dependencies.
- **No Network**: Tests shall not call real OpenRouter, OpenAI, or other providers.
- **Constructor Inspection Strategy**: Prefer patching `NormalizedChatOpenAI` or inspecting the returned instance attributes so tests assert the actual kwargs sent into model construction.
- **Coverage Focus**:
  - `openrouter_reasoning_effort` default and propagation.
  - No top-level `reasoning_effort` leakage for OpenRouter.
  - `extra_body` merge behavior.
  - ValueError for malformed `extra_body["reasoning"]`.
  - No regression in native OpenAI `reasoning_effort` behavior.

Recommended tests:

- `test_provider_kwargs_include_openrouter_reasoning_effort()`
- `test_provider_kwargs_skip_openrouter_reasoning_when_not_configured()`
- `test_openrouter_client_translates_reasoning_effort_to_extra_body()`
- `test_openrouter_client_merges_existing_extra_body()`
- `test_openrouter_client_merges_existing_reasoning_mapping()`
- `test_openrouter_client_raises_for_non_mapping_reasoning_block()`
- `test_native_openai_client_keeps_reasoning_effort_and_responses_api()`

Recommended focused validation commands during implementation:

```bash
uv run --with pytest pytest tests/test_graph_provider_kwargs.py tests/test_openai_client.py tests/test_provider_reasoning_config.py
```

If `tests/test_provider_reasoning_config.py` is not created, use the narrower set of touched files instead.

## 7. Rationale & Context

TradingAgents currently supports native OpenAI reasoning effort by reading `openai_reasoning_effort` in the graph layer and forwarding a top-level `reasoning_effort` kwarg into the OpenAI client path. That behavior is appropriate for native OpenAI because the native provider path opts into the Responses API.

OpenRouter is different in two ways:

- It stays on Chat Completions rather than the Responses API.
- Its documented reasoning control is a nested `reasoning` object that is typically supplied through `extra_body` when using the OpenAI Python SDK or LangChain's `ChatOpenAI` wrapper.

The root cause of the current missing feature is that TradingAgents has no OpenRouter-specific reasoning config key and no translation step from semantic reasoning settings into OpenRouter's request-body shape.

The preferred design is therefore:

- separate config key for OpenRouter,
- semantic propagation through the graph,
- provider-specific wire-format translation in the OpenRouter client.

This preserves clean separation of concerns:

- CLI collects user intent,
- graph assembles semantic provider settings,
- client translates those settings into provider-specific SDK kwargs.

## 8. Dependencies & External Integrations

### External Systems

- **EXT-001**: OpenRouter Chat Completions API at `https://openrouter.ai/api/v1`.

### Third-Party Services

- **SVC-001**: OpenRouter model routing and reasoning feature support, including provider-specific model capability mapping.

### Infrastructure Dependencies

- **INF-001**: Environment variable `OPENROUTER_API_KEY` for authenticated OpenRouter requests.

### Technology Platform Dependencies

- **PLT-001**: `langchain-openai` support for `extra_body` on `ChatOpenAI`.
- **PLT-002**: OpenAI Python SDK support for `extra_body` passthrough on Chat Completions.
- **PLT-003**: Existing TradingAgents OpenAI-compatible client abstraction in `tradingagents/llm_clients/openai_client.py`.

### Compliance Dependencies

- **COM-001**: No additional compliance requirements are introduced by this feature beyond the repository's existing research-framework disclaimer.

## 9. Examples & Edge Cases

Example configuration:

```python
config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openrouter"
config["quick_think_llm"] = "openai/gpt-5-mini"
config["deep_think_llm"] = "anthropic/claude-sonnet-4.5"
config["openrouter_reasoning_effort"] = "minimal"
```

Example translated kwargs:

```python
{
    "model": "openai/gpt-5-mini",
    "base_url": "https://openrouter.ai/api/v1",
    "api_key": "test-key",
    "extra_body": {
        "reasoning": {
            "effort": "minimal",
        }
    },
}
```

Edge cases:

- If `openrouter_reasoning_effort` is unset, no reasoning block is added.
- If `openrouter_reasoning_effort == "none"`, TradingAgents still sends the reasoning block because that value explicitly disables reasoning in OpenRouter's documented schema.
- If the selected OpenRouter model ignores or down-maps the requested effort, TradingAgents shall not treat that as an application error. The request shape is still valid.
- If `extra_body` already contains unrelated provider settings, they must survive the merge.
- If `extra_body["reasoning"]` is not a mapping, the implementation should fail fast with a clear error.
- Returned reasoning tokens, if any, remain out of scope for display or persistence.

## 10. Validation Criteria

- All new or updated reasoning-support tests shall pass locally.
- No existing tests for native OpenAI, Google, Anthropic, or model validation shall regress.
- The OpenRouter client path shall construct `extra_body.reasoning.effort` only when configured.
- The OpenRouter client path shall not set `use_responses_api`.
- The native OpenAI client path shall continue to set `use_responses_api` and honor top-level `reasoning_effort`.
- Documentation updates shall clearly distinguish OpenRouter reasoning support from native OpenAI reasoning support.

## 11. Related Specifications / Further Reading

- [README.md](../README.md)
- [docs/user-guide.md](../docs/user-guide.md)
- OpenRouter Reasoning Tokens documentation: https://openrouter.ai/docs/use-cases/reasoning-tokens
- OpenRouter API overview: https://openrouter.ai/docs/api-reference/overview
