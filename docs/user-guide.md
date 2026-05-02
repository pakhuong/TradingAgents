# TradingAgents User Guide

This guide covers the practical workflow for running TradingAgents from the command line, saving reports, and handling the most common setup choices.

TradingAgents is a research framework, not financial advice. Outputs depend on model choice, data quality, and market conditions.

## Table of Contents

1. Overview
2. Prerequisites
3. Install the Project
4. Configure API Keys
5. Run Your First Analysis
6. Understand the Results
7. Common Workflows
8. Python Usage
9. Troubleshooting

## Overview

TradingAgents runs a multi-agent trading workflow made up of:

- Analyst agents for market, social sentiment, news, and fundamentals
- Bull and bear researchers plus a research manager
- A trader agent that turns research into a trading plan
- Risk and portfolio agents that produce the final decision

The main user interface is an interactive terminal application. You choose a ticker, date, provider, and model settings, then watch the agent teams work through the analysis live.

![TradingAgents CLI start screen](../assets/cli/cli_init.png)

## Prerequisites

You need:

- Python 3.10 or newer
- At least one supported LLM API key
- Network access for your selected model provider and market data sources

Supported LLM providers include OpenAI, Google, Anthropic, xAI, DeepSeek, Qwen, GLM, OpenRouter, Ollama, and Azure OpenAI.

By default, market data is fetched through yfinance. Vietnam market symbols can be routed through vnstock when the optional extra is installed.

## Install the Project

### Recommended: uv

```bash
git clone https://github.com/TauricResearch/TradingAgents.git
cd TradingAgents
uv sync
```

If you plan to analyze Vietnam-listed symbols such as `HOSE:FPT` or `VNINDEX`, install the optional extra:

```bash
uv sync --extra vietnam
```

### Alternative: pip

```bash
git clone https://github.com/TauricResearch/TradingAgents.git
cd TradingAgents
pip install -e .
```

For Vietnam data with pip:

```bash
pip install -e ".[vietnam]"
```

## Configure API Keys

Copy the example environment file and fill in the credentials for the provider you actually plan to use:

```bash
cp .env.example .env
```

The standard `.env` file supports these keys:

```dotenv
OPENAI_API_KEY=
GOOGLE_API_KEY=
ANTHROPIC_API_KEY=
XAI_API_KEY=
DEEPSEEK_API_KEY=
DASHSCOPE_API_KEY=
ZHIPU_API_KEY=
OPENROUTER_API_KEY=
VNSTOCK_API_KEY=
```

If you use Azure OpenAI, also create the enterprise config file:

```bash
cp .env.enterprise.example .env.enterprise
```

Then set the Azure-specific values:

```dotenv
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=
```

Notes:

- You only need to populate the provider you intend to use.
- `ALPHA_VANTAGE_API_KEY` is optional and only needed if you switch data vendors to Alpha Vantage.
- `VNSTOCK_API_KEY` is optional and only needed if you want TradingAgents to auto-register vnstock for higher vnstock usage limits. Leave it unset to use vnstock guest mode.
- Ollama does not require a cloud API key, but it does require a reachable local Ollama server and an installed local model.

## Run Your First Analysis

After installation, start the interactive CLI:

```bash
uv run tradingagents
```

If you installed with `pip`, the direct command also works:

```bash
tradingagents
```

You can also run it from source:

```bash
uv run python -m cli.main
```

### Interactive flow

The CLI walks through the analysis in eight steps:

1. Ticker symbol
2. Analysis date in `YYYY-MM-DD` format
3. Output language
4. Which analyst agents to enable
5. Research depth
6. LLM provider
7. Quick and deep thinking models
8. Provider-specific reasoning settings when applicable

### Choosing research depth

Research depth is one of the highest-impact settings in the CLI. It does not change which agents run. It changes how much back-and-forth happens before TradingAgents moves on to the next stage.

Under the hood, this choice is applied to both the research debate and the risk discussion:

- `Shallow` sets the depth to `1`
- `Medium` sets the depth to `3`
- `Deep` sets the depth to `5`

That value is used for both:

- `max_debate_rounds` for the bull-versus-bear research debate
- `max_risk_discuss_rounds` for the aggressive, conservative, and neutral risk discussion

In practice, higher research depth means:

- more agent turns before the Research Manager and Portfolio Manager finalize their decisions
- longer runtime
- higher token usage and model cost
- more opportunities for the agents to challenge weak assumptions or refine the thesis

Use each option this way:

- `Shallow`: fastest path, best for smoke runs, provider checks, and quick directional reads
- `Medium`: balanced option for most day-to-day analysis runs
- `Deep`: slowest and most expensive option, best when you want more adversarial debate before acting on the result

If this is your first run, `Medium` is the safest default. Use `Shallow` when you are validating setup, and switch to `Deep` only when the additional time and cost are justified.

Provider-specific settings appear only when they are relevant:

- Google: Gemini thinking mode
- OpenAI: reasoning effort
- Anthropic: effort level

The analysis date cannot be in the future. Explicit Vietnam tickers such as `HOSE:FPT`, `HNX:SHS`, `VNINDEX`, and `VN30` automatically switch the run to the Vietnam market profile.

### What you see during the run

Once the run starts, the terminal shows:

- Agent progress by team
- Recent messages and tool calls
- The latest report section as it is produced
- Runtime and token statistics in the footer

![TradingAgents live progress view](../assets/cli/cli_news.png)

At the end of the run, the CLI asks whether to save the report and whether to display the complete report in the terminal.

![TradingAgents final decision view](../assets/cli/cli_transaction.png)

## Understand the Results

If you choose to save the report, the CLI proposes a default output path like:

```text
./reports/SPY_20260502_153000/
```

Saved runs are organized into these folders:

- `1_analysts/` for market, sentiment, news, and fundamentals reports
- `2_research/` for bull, bear, and research-manager outputs
- `3_trading/` for the trader plan
- `4_risk/` for aggressive, neutral, and conservative risk views
- `5_portfolio/` for the portfolio manager decision
- `complete_report.md` for a consolidated report file

The final portfolio decision uses the five-tier rating scale introduced in recent releases:

- Buy
- Overweight
- Hold
- Underweight
- Sell

## Common Workflows

### Run a standard US equity analysis

```bash
uv run tradingagents
```

Suggested first run:

- Ticker: `SPY` or `NVDA`
- Date: today or a recent trading day
- Analysts: all enabled
- Provider: a model family you already have credentials for

### Resume an interrupted run

Enable checkpointing to save state after each graph node:

```bash
uv run tradingagents --checkpoint
```

Checkpoint files are stored under `~/.tradingagents/cache/checkpoints/` by default.

If you want to discard old checkpoints and start fresh:

```bash
uv run tradingagents --clear-checkpoints
```

You can combine both options when needed:

```bash
uv run tradingagents --clear-checkpoints --checkpoint
```

### Analyze Vietnam-listed symbols

Install the Vietnam extra first:

```bash
uv sync --extra vietnam
```

Then run the CLI and enter a supported symbol such as:

- `HOSE:FPT`
- `HNX:SHS`
- `VIC.HM`
- `VNINDEX`
- `VN30`

Explicit Vietnam symbols automatically switch to the Vietnam profile, which uses `VNINDEX` as the benchmark and `VND` as the currency.

### Run with Docker

For containerized usage:

```bash
cp .env.example .env
docker compose run --rm tradingagents
```

For local Ollama models through the Docker profile:

```bash
docker compose --profile ollama run --rm tradingagents-ollama
```

## Python Usage

You can also drive the framework programmatically:

```python
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"
config["deep_think_llm"] = "gpt-5.4"
config["quick_think_llm"] = "gpt-5.4-mini"

graph = TradingAgentsGraph(debug=True, config=config)
state, decision = graph.propagate("NVDA", "2026-01-15")
print(decision)
```

Useful config keys include:

- `llm_provider`
- `deep_think_llm`
- `quick_think_llm`
- `llm_timeout`
- `max_debate_rounds`
- `output_language`
- `checkpoint_enabled`
- `data_vendors`
- `tool_vendors`

Environment overrides are also available for persistent paths:

- `TRADINGAGENTS_RESULTS_DIR`
- `TRADINGAGENTS_CACHE_DIR`
- `TRADINGAGENTS_MEMORY_LOG_PATH`

## Troubleshooting

### The CLI starts but the run fails immediately

Check that the API key for your chosen provider is set in `.env` or your shell environment. If you selected OpenAI, for example, `OPENAI_API_KEY` must be present.

### The CLI rejects my date

TradingAgents only accepts dates in `YYYY-MM-DD` format, and the date cannot be in the future.

### Vietnam symbols return no useful data

Install the optional Vietnam dependency:

```bash
uv sync --extra vietnam
```

Without `vnstock`, explicit Vietnam symbols can fail or return empty data through generic vendors.

### A previous interrupted run keeps resuming

Clear old checkpoints before starting again:

```bash
uv run tradingagents --clear-checkpoints
```

### Model calls hang too long

The default per-call LLM timeout is `30` seconds. If you are using the Python API, you can override it through `config["llm_timeout"]`.

### Where are memory and cache files stored?

By default, TradingAgents stores persistent data under `~/.tradingagents/`, including:

- cache files
- checkpoint databases
- the persistent trading memory log

## Next Steps

After your first successful run, the most useful next experiments are:

1. Compare the same ticker across two providers or model pairs.
2. Turn on checkpoints for longer runs or less stable environments.
3. Try an explicit Vietnam ticker with the optional market-data extra installed.
