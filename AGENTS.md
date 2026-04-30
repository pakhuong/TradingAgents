# Project Guidelines

## Build And Test

- Install or refresh the environment with `uv sync`. If `uv` is unavailable, use `pip install -e .` from the repository root.
- Run the test suite with `uv run pytest` or `pytest`. Pytest markers are `unit`, `integration`, and `smoke`; prefer focused marker/path runs while iterating.
- Run the CLI with `uv run tradingagents` after installation, or `uv run python -m cli.main` directly from source.
- Use `scripts/smoke_structured_output.py` only when validating real structured-output provider behavior; it needs real API keys and may make paid LLM calls.
- Docker and user-facing setup details live in [README.md](README.md); recent behavior changes and migration notes live in [CHANGELOG.md](CHANGELOG.md).

## Architecture

- `tradingagents/graph/` owns LangGraph orchestration, checkpoint resume, propagation, reflection, and final signal processing.
- `tradingagents/agents/` contains role-specific agent factory functions. Shared state types live in `tradingagents/agents/utils/agent_states.py`; typed decision schemas live in `tradingagents/agents/schemas.py`.
- `tradingagents/dataflows/` is the data access layer. Keep vendor routing behind `data_vendors` and `tool_vendors` config instead of hardcoding providers inside agents.
- `tradingagents/llm_clients/` is the multi-provider LLM layer. Provider modules are imported lazily in the factory so test collection works without optional SDK side effects.
- `cli/` is the Typer/Rich interactive interface and package entry point (`tradingagents = cli.main:app`).

## Project Conventions

- Start config customizations from `DEFAULT_CONFIG.copy()` before mutation. Important env overrides include `TRADINGAGENTS_RESULTS_DIR`, `TRADINGAGENTS_CACHE_DIR`, and `TRADINGAGENTS_MEMORY_LOG_PATH`.
- Preserve explicit `encoding="utf-8"` for file I/O; this project intentionally avoids platform-default encodings.
- Unit tests should not require real credentials. `tests/conftest.py` supplies placeholder API keys and mock LLM helpers; keep imports lazy where possible.
- For structured-output decision agents, use `bind_structured` and `invoke_structured_or_freetext` from `tradingagents/agents/utils/structured.py`, then render typed results back to the markdown shape consumed by the CLI, memory log, reports, and smoke checks.
- Checkpoint resume stores per-ticker SQLite files under `~/.tradingagents/cache/checkpoints/` by default. Successful runs clear checkpoints; `--clear-checkpoints` resets them before a CLI run.
- The persistent decision log replaces older per-agent memory. Portfolio Manager is the memory consumer, and prior decisions are only injected when entries exist.
- Internal agent debate stays in English for reasoning quality; `output_language` controls user-facing reports and final decisions.
- Preserve exchange-qualified ticker symbols such as `7203.T` and `BRK.B`; do not strip suffixes or dots during validation, prompt construction, or tool routing.
- Treat the project as a research framework, not financial advice. Keep user-facing docs aligned with the disclaimer in [README.md](README.md).
