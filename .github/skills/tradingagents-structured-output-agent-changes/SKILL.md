---
name: tradingagents-structured-output-agent-changes
description: "Use when: modifying TradingAgents structured-output decision agents, Pydantic schemas, render helpers, Research Manager, Trader, Portfolio Manager prompts, rating parsing, memory-log integration, or structured-output smoke tests. Guides schema/render/prompt/test updates for ResearchPlan, TraderProposal, and PortfolioDecision."
argument-hint: "Describe the structured-output agent change or schema/prompt behavior to update"
---

# TradingAgents Structured-Output Agent Changes

## Outcome

Use this skill to make changes to the structured-output decision path without breaking downstream markdown consumers. The expected result is a focused change where schemas, renderers, prompts, parser behavior, and tests stay aligned.

## When To Use

- Adding, renaming, or removing fields in `ResearchPlan`, `TraderProposal`, or `PortfolioDecision`.
- Changing Research Manager, Trader, or Portfolio Manager prompts.
- Updating the 5-tier rating vocabulary, trader action vocabulary, or rating parser.
- Fixing structured-output provider fallback behavior.
- Adjusting memory-log or signal-processing behavior that consumes final decision markdown.

## Key Files

- `tradingagents/agents/schemas.py`: Pydantic schemas, enums, and markdown render helpers.
- `tradingagents/agents/utils/structured.py`: `bind_structured` and `invoke_structured_or_freetext` fallback pattern.
- `tradingagents/agents/managers/research_manager.py`: debate history to `ResearchPlan` to rendered `investment_plan`.
- `tradingagents/agents/trader/trader.py`: `investment_plan` to `TraderProposal` to rendered `trader_investment_plan`.
- `tradingagents/agents/managers/portfolio_manager.py`: risk debate, trader proposal, and memory context to rendered `final_trade_decision`.
- `tradingagents/agents/utils/rating.py`: deterministic 5-tier rating extraction.
- `tradingagents/graph/signal_processing.py`: adapter over rating parsing; should not add LLM calls.
- `tradingagents/agents/utils/memory.py`: stores parsed final ratings and injects prior lessons.
- `tests/test_structured_agents.py`, `tests/test_signal_processing.py`, and `tests/test_memory_log.py`: fast validation coverage.
- `scripts/smoke_structured_output.py`: opt-in real-provider smoke script.

## Procedure

1. Identify the structured artifact being changed.
   - Research Manager uses `ResearchPlan` and `render_research_plan`.
   - Trader uses `TraderProposal` and `render_trader_proposal`.
   - Portfolio Manager uses `PortfolioDecision` and `render_pm_decision`.

2. Update schemas and render helpers together.
   - Edit `tradingagents/agents/schemas.py` first.
   - Keep enum values stable unless the task explicitly changes public behavior.
   - If a field is optional, add a default and render it conditionally.
   - If a field is required, update prompts and tests in the same change.
   - Preserve markdown headers consumed downstream: `**Recommendation**`, `**Action**`, `FINAL TRANSACTION PROPOSAL: **...**`, `**Rating**`, `**Executive Summary**`, and `**Investment Thesis**`.

3. Align prompts with the schema.
   - For Research Manager and Portfolio Manager, keep all five rating tiers visible in prompt text: Buy, Overweight, Hold, Underweight, Sell.
   - For Trader, keep action guidance ternary: Buy, Hold, Sell.
   - Keep internal debate/reasoning prompts in English; `output_language` applies to user-facing output.
   - Preserve exchange-qualified ticker context from `build_instrument_context`; do not strip symbols like `7203.T` or `BRK.B`.

4. Preserve the structured fallback pattern.
   - Bind once when creating the agent with `bind_structured(llm, Schema, "Agent Name")`.
   - Invoke with `invoke_structured_or_freetext(structured_llm, llm, prompt, render_func, "Agent Name")`.
   - Render typed Pydantic results to markdown before returning state values.
   - Do not pass Pydantic instances into memory log, CLI display, saved reports, or graph state.

5. Check downstream consumers.
   - If Portfolio Manager output changes, ensure `parse_rating` still extracts the final rating.
   - `SignalProcessor` should remain deterministic and should not invoke an LLM.
   - If memory behavior changes, confirm `TradingMemoryLog.store_decision` still receives rendered markdown and uses explicit `encoding="utf-8"` for file I/O.
   - If prior lessons are involved, verify `past_context` is injected only when non-empty.

6. Add or update tests at the smallest useful scope.
   - Render changes: add assertions in `tests/test_structured_agents.py` or `tests/test_memory_log.py` for Portfolio Manager output.
   - Prompt changes: capture mock LLM prompts and assert required rating/action guidance is present.
   - Fallback changes: mock `with_structured_output` to raise `NotImplementedError` and assert free-text output is returned.
   - Rating parser changes: update `tests/test_signal_processing.py::TestParseRating`.
   - Memory injection changes: update `tests/test_memory_log.py::TestPortfolioManagerInjection`.

7. Validate locally.
   - Prefer focused unit tests while iterating:
     ```bash
     uv run pytest tests/test_structured_agents.py -v
     uv run pytest tests/test_signal_processing.py::TestParseRating -v
     uv run pytest tests/test_memory_log.py -k portfolio_manager -v
     ```
   - Run broader tests when the change touches shared contracts:
     ```bash
     uv run pytest tests/test_structured_agents.py tests/test_signal_processing.py tests/test_memory_log.py -v
     ```
   - Run `scripts/smoke_structured_output.py` only when intentionally validating real provider behavior with real API keys, because it can make paid LLM calls.

## Decision Points

- New schema field: make it optional when downstream consumers can ignore it; make it required only when every provider prompt, renderer, and test is updated.
- Changed markdown header: avoid this unless the task is a migration; update parser, memory log expectations, saved report assumptions, and tests together.
- Provider structured-output failure: preserve graceful fallback unless the task explicitly requires failing closed.
- Rating vocabulary change: update schema enum, prompt text, `RATINGS_5_TIER`, parser tests, memory log expectations, and signal-processing tests together.
- Real-provider validation: use the smoke script only after unit tests pass and credentials are available.

## Completion Checklist

- Schema descriptions, prompt instructions, render output, and tests describe the same behavior.
- Rendered markdown remains the graph state and persistence format.
- `parse_rating` recognizes the Portfolio Manager markdown shape.
- Fallback behavior is tested for unsupported structured output.
- File I/O keeps explicit `encoding="utf-8"`.
- Focused pytest commands pass or any unrun tests are called out clearly.
