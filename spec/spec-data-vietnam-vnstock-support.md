---
title: Vietnam Equity Market Data Support With vnstock
version: 1.1
date_created: 2026-04-30
last_updated: 2026-04-30
owner: TradingAgents maintainers
tags: [data, vietnam, vnstock, market-support, vendor-adapter]
---

# Introduction

This specification defines how a coding agent shall add Vietnamese stock market support to TradingAgents by integrating `vnstock` as a new data vendor. The implementation shall preserve the existing vendor-router architecture, avoid hardcoded provider logic inside agents, and support Vietnam-listed equities with local symbols such as `FPT`, `VNM`, `TCB`, and index symbols such as `VNINDEX` or `VN30`.

## 1. Purpose & Scope

This specification applies to the TradingAgents Python repository. It is intended for a coding agent implementing a first production-quality pass of Vietnam market support.

The scope includes:

- Adding a `vnstock` data vendor adapter under `tradingagents/dataflows/`.
- Routing Vietnam-capable stock, technical indicator, fundamental, and news methods through `tradingagents/dataflows/interface.py`.
- Adding market profile configuration for Vietnam, including native currency and benchmark index.
- Automatically applying the Vietnam market profile for explicit Vietnam symbols before graph data fetches, including memory-log outcome resolution.
- Preventing explicit Vietnam symbols from leaking to yfinance or Alpha Vantage fallback paths that are known to produce invalid-symbol errors for forms such as `HOSE:VIC`.
- Updating CLI examples and agent instrument context so Vietnam symbols are preserved and interpreted correctly.
- Replacing the hardcoded `SPY` benchmark in memory-log outcome resolution with a configurable benchmark, defaulting to `SPY` for existing behavior and `VNINDEX` for Vietnam.
- Adding focused unit tests that mock `vnstock` and do not require real network access or credentials.
- Updating documentation and dependency declarations as needed.

The scope excludes:

- Live trading integration.
- Broker order placement.
- Paid FiinQuant, SSI FastConnect, Vietstock DataFeed, or EODHD integration.
- A full market screener or portfolio optimizer for Vietnam.
- Real credential-dependent integration tests in the default test suite.

## 2. Definitions

- **TradingAgents**: The multi-agent trading research framework in this repository.
- **Vendor router**: The routing layer in `tradingagents/dataflows/interface.py` that dispatches tool calls to configured data providers.
- **vnstock**: A Python toolkit for Vietnamese financial market data. It provides access to historical prices, intraday data, financial statements, ratios, company information, market indices, and related datasets through Pandas-friendly APIs.
- **Vietnam-listed equity**: A stock listed on HOSE, HNX, or UPCOM.
- **HOSE**: Ho Chi Minh Stock Exchange.
- **HNX**: Hanoi Stock Exchange.
- **UPCOM**: Unlisted Public Company Market.
- **VNINDEX**: Vietnam Ho Chi Minh Stock Index, used as the default Vietnam market benchmark in this specification.
- **OHLCV**: Open, high, low, close, and volume price data.
- **VND**: Vietnamese dong, the native currency for Vietnam equity prices.
- **Provider symbol**: The exact symbol format expected by a data provider. For `vnstock`, common Vietnam equity symbols are unqualified uppercase local codes such as `FPT`, `VNM`, and `TCB`.
- **Explicit Vietnam symbol**: A user-facing ticker that unambiguously identifies the Vietnam market without external context. Explicit forms include `HOSE:<symbol>`, `HSX:<symbol>`, `HNX:<symbol>`, `UPCOM:<symbol>`, `.HM`, `.HN`, `.UPCOM`, `VNINDEX`, and `VN30`. Plain local codes such as `FPT` and `VIC` are valid Vietnam symbols but are not explicit because they may be ambiguous without user configuration.

## 3. Requirements, Constraints & Guidelines

### Functional Requirements

- **REQ-001**: Add `vnstock` as a supported vendor in `tradingagents/dataflows/interface.py`.
- **REQ-002**: Implement a new adapter module at `tradingagents/dataflows/vnstock.py`.
- **REQ-003**: The `vnstock` adapter shall expose vendor functions compatible with the current router method signatures:
  - `get_stock(symbol: str, start_date: str, end_date: str) -> str`
  - `get_indicator(symbol: str, indicator: str, curr_date: str, look_back_days: int) -> str`
  - `get_fundamentals(ticker: str, curr_date: str | None = None) -> str`
  - `get_balance_sheet(ticker: str, freq: str = "quarterly", curr_date: str | None = None) -> str`
  - `get_cashflow(ticker: str, freq: str = "quarterly", curr_date: str | None = None) -> str`
  - `get_income_statement(ticker: str, freq: str = "quarterly", curr_date: str | None = None) -> str`
  - `get_news(ticker: str, start_date: str, end_date: str) -> str`
  - `get_global_news(curr_date: str, look_back_days: int = 7, limit: int = 10) -> str`
  - `get_insider_transactions(ticker: str) -> str`
- **REQ-004**: The `vnstock` adapter shall return strings matching the style expected by existing tools: Markdown headers plus CSV or concise labeled text.
- **REQ-005**: The `vnstock` adapter shall normalize OHLCV data to a CSV shape compatible with current downstream expectations: `Date`, `Open`, `High`, `Low`, `Close`, and `Volume` where data is available.
- **REQ-006**: The `vnstock` adapter shall preserve Vietnam local symbols without appending yfinance suffixes such as `.HM` or `.HN`.
- **REQ-007**: The `vnstock` adapter shall tolerate exchange-qualified user input forms when practical, such as `HOSE:FPT`, `HNX:SHS`, `UPCOM:ABC`, `FPT.HM`, and `SHS.HN`, by mapping them to the provider symbol expected by `vnstock` before provider calls.
- **REQ-008**: The `vnstock` adapter shall support Vietnam market index symbols needed for benchmark use, including at least `VNINDEX` and `VN30` if supported by the installed `vnstock` version.
- **REQ-009**: Technical indicators for `vnstock` data shall be calculated locally from OHLCV data using the same indicator behavior as the current yfinance path when provider-side indicators are not available.
- **REQ-010**: Add a market profile configuration that can represent Vietnam without breaking existing US/default behavior.
- **REQ-011**: Replace hardcoded alpha-vs-`SPY` behavior with a configurable benchmark symbol.
- **REQ-012**: Vietnam profile defaults shall use `VNINDEX` as the benchmark and `VND` as the currency.
- **REQ-013**: Agent prompts and tool descriptions shall continue to instruct agents to use exact user-provided tickers while adding Vietnam examples.
- **REQ-014**: CLI ticker examples shall include Vietnam symbols such as `FPT`, `VNM`, or `HOSE:FPT`.
- **REQ-015**: Documentation shall explain how to enable `vnstock` through `data_vendors` and `tool_vendors` config.
- **REQ-016**: Shared configuration helpers shall detect explicit Vietnam symbols and apply the Vietnam profile consistently for CLI and programmatic graph runs.
- **REQ-017**: `TradingAgentsGraph.propagate()` shall apply the Vietnam profile for explicit Vietnam symbols before any ticker-scoped data fetch, including pending memory-log outcome resolution.
- **REQ-018**: The vendor router shall force ticker-scoped requests for explicit Vietnam symbols to `vnstock` when a `vnstock` implementation exists, even when the current vendor configuration starts with yfinance or Alpha Vantage.
- **REQ-019**: The `vnstock` adapter shall return a clear unsupported-data message for insider transactions instead of allowing explicit Vietnam symbols to fall through to yfinance.

### Compatibility Requirements

- **CMP-001**: Existing yfinance and Alpha Vantage behavior shall remain unchanged for non-Vietnam workflows and non-explicit symbols when `vnstock` is not selected. Explicit Vietnam symbols are intentionally routed to `vnstock` to avoid known invalid yfinance or Alpha Vantage calls.
- **CMP-002**: Existing tests for exchange-qualified tickers such as `7203.T` and `BRK.B` shall continue to pass.
- **CMP-003**: The default configuration shall not force all users onto Vietnam market behavior.
- **CMP-004**: Unit tests shall not require network calls to `vnstock`, yfinance, Alpha Vantage, or any paid provider.

### Constraints

- **CON-001**: Do not hardcode provider selection inside agent files under `tradingagents/agents/`. Use the vendor router.
- **CON-002**: Do not require real credentials for the default test suite.
- **CON-003**: Do not remove yfinance or Alpha Vantage vendor support.
- **CON-004**: Do not strip dots from non-Vietnam exchange-qualified symbols. Symbols such as `7203.T` and `BRK.B` must remain valid.
- **CON-005**: Preserve explicit `encoding="utf-8"` for file I/O.
- **CON-006**: Prefer lazy imports for `vnstock` so test collection works even when the optional provider is not installed, unless the package is made a mandatory dependency.
- **CON-007**: Do not add paid provider calls or live credentials to examples.

### Guidelines

- **GUD-001**: Prefer a small, focused `vnstock` adapter over broad refactoring of the dataflow layer.
- **GUD-002**: Use helper functions for symbol normalization and DataFrame normalization inside the adapter.
- **GUD-003**: Use structured Pandas operations for DataFrame conversion instead of ad hoc string manipulation.
- **GUD-004**: When `vnstock` lacks a dataset, return a clear Markdown message rather than crashing, unless the error indicates a coding defect.
- **GUD-005**: Treat `vnstock` as a research data source. Documentation must preserve the project disclaimer that this is not financial advice.
- **GUD-006**: Add FiinQuant or SSI FastConnect only in future work. The first implementation shall be `vnstock` only.

## 4. Interfaces & Data Contracts

### 4.1 Configuration Contract

Update `tradingagents/default_config.py` with market-aware fields while preserving defaults.

Required keys:

```python
DEFAULT_CONFIG = {
    # existing keys...
    "market_profile": "default",
    "benchmark_symbol": "SPY",
    "currency": "USD",
    "data_vendors": {
        "core_stock_apis": "yfinance",
        "technical_indicators": "yfinance",
        "fundamental_data": "yfinance",
        "news_data": "yfinance",
    },
}
```

Recommended Vietnam override example:

```python
config = DEFAULT_CONFIG.copy()
config["market_profile"] = "vietnam"
config["benchmark_symbol"] = "VNINDEX"
config["currency"] = "VND"
config["data_vendors"] = {
    "core_stock_apis": "vnstock,yfinance",
    "technical_indicators": "vnstock,yfinance",
    "fundamental_data": "vnstock,yfinance",
    "news_data": "vnstock,yfinance",
}
```

The router already supports comma-separated fallback vendors. The implementation shall preserve this behavior.

Shared Vietnam profile helpers shall live in `tradingagents/default_config.py` or an equivalent core configuration module so CLI and programmatic graph runs use the same detection rules:

```python
def normalize_ticker_symbol(ticker: str) -> str:
    """Normalize ticker input while preserving exchange suffixes."""


def is_explicit_vietnam_symbol(ticker: str) -> bool:
    """Return True for explicit Vietnam forms such as HOSE:FPT, FPT.HM, VNINDEX, or VN30."""


def apply_market_profile_for_symbol(config: dict, ticker: str) -> bool:
    """Mutate config to the Vietnam profile when ticker is an explicit Vietnam symbol."""
```

`TradingAgentsGraph.propagate(company_name, trade_date)` shall call the shared profile helper after the run ticker is known and before `_resolve_pending_entries(company_name)` or any analyst tool execution. This ensures that both historical outcome resolution and live analyst tools use `VNINDEX` and the `vnstock,yfinance` vendor chain for explicit Vietnam tickers. Plain local symbols such as `FPT` and `VIC` remain configuration-driven unless the user explicitly sets the Vietnam profile.

### 4.2 Vendor Router Contract

Update `tradingagents/dataflows/interface.py`:

- Import functions from `tradingagents/dataflows/vnstock.py` using aliases such as `get_vnstock_stock`.
- Add `"vnstock"` to `VENDOR_LIST`.
- Add `"vnstock"` implementations to `VENDOR_METHODS` for:
  - `get_stock_data`
  - `get_indicators`
  - `get_fundamentals`
  - `get_balance_sheet`
  - `get_cashflow`
  - `get_income_statement`
  - `get_news`
  - `get_global_news`
  - `get_insider_transactions`
- Add a provider-unavailable fallback path if `vnstock` is optional. For non-explicit symbols, the router shall continue to the next configured vendor when the primary vendor raises a provider-unavailable exception caused by a missing optional dependency.
- Add an explicit Vietnam symbol guard for ticker-scoped methods. For explicit Vietnam symbols and methods with a `vnstock` implementation, the router shall skip non-`vnstock` vendors even if the configured chain starts with yfinance or Alpha Vantage. This prevents invalid yfinance requests such as `HOSE:VIC`. Graph-time profile application covers later plain-symbol calls such as `VIC` during the same explicit Vietnam run. `get_global_news` is not ticker-scoped and is excluded from this guard.

Recommended router behavior:

```python
class DataVendorUnavailableError(Exception):
    """Raised when a configured vendor cannot run in the current environment."""


explicit_vietnam_symbol = (
    method in ticker_scoped_methods
    and is_explicit_vietnam_symbol(first_arg)
    and "vnstock" in vendor_methods_for_method
)

for vendor in fallback_vendors:
    if explicit_vietnam_symbol and vendor != "vnstock":
        continue
    try:
        return impl_func(*args, **kwargs)
    except (AlphaVantageRateLimitError, DataVendorUnavailableError):
        continue
```

For explicit Vietnam symbols, if `vnstock` is unavailable, the router shall not silently fall back to yfinance. It shall fail with a clear unavailable-vendor outcome so callers can install the Vietnam extra or choose a non-explicit/configured fallback deliberately.

The implementation may place `DataVendorUnavailableError` in `tradingagents/dataflows/interface.py` or a small shared module if that produces cleaner imports.

### 4.3 vnstock Adapter Contract

Create `tradingagents/dataflows/vnstock.py`.

The module shall contain small helper functions. Recommended helpers:

```python
def _load_vnstock():
    """Import vnstock lazily and raise DataVendorUnavailableError if unavailable."""


def _normalize_vietnam_symbol(symbol: str) -> str:
    """Map user/provider variants to vnstock local symbols."""


def _normalize_ohlcv(data: pandas.DataFrame) -> pandas.DataFrame:
    """Return Date/Open/High/Low/Close/Volume columns when present."""


def _format_csv_report(title: str, data: pandas.DataFrame) -> str:
    """Return Markdown title plus CSV content."""
```

The adapter shall use the current public `vnstock` API at implementation time. Known usage patterns from current public docs include:

```python
from vnstock import Vnstock, Quote

stock = Vnstock().stock(symbol="FPT", source="VCI")
price_history = stock.quote.history(start="2024-01-01", end="2024-12-31")
balance_sheet = stock.finance.balance_sheet(period="quarter", lang="en", dropna=True)
income_statement = stock.finance.income_statement(period="quarter", lang="en", dropna=True)
cash_flow = stock.finance.cash_flow(period="quarter", dropna=True)
ratios = stock.finance.ratio(period="quarter", lang="en", dropna=True)
```

The coding agent shall verify exact method names against the installed `vnstock` version before implementing. If the installed package exposes a different API, adapt the wrapper while preserving the TradingAgents function signatures.

### 4.4 OHLCV Data Contract

`get_stock(symbol, start_date, end_date)` shall return a string with this structure:

```text
# Stock data for FPT from 2026-01-01 to 2026-01-31
# Vendor: vnstock
# Currency: VND
# Total records: 20
# Data retrieved on: 2026-04-30 HH:MM:SS

Date,Open,High,Low,Close,Volume
2026-01-02,100000,101000,99500,100500,1234567
```

Rules:

- Dates shall be parsed to `YYYY-MM-DD` when possible.
- Numeric values shall remain numeric in CSV output.
- Provider column names such as `time`, `date`, `open`, `high`, `low`, `close`, and `volume` shall be normalized to title-case canonical names.
- Rows after `end_date` shall not appear.
- Rows before `start_date` shall not appear.
- Empty data shall return `No data found for symbol '<symbol>' between <start_date> and <end_date>`.

### 4.5 Technical Indicator Contract

`get_indicator(symbol, indicator, curr_date, look_back_days)` shall return the same style as the yfinance indicator implementation:

```text
## rsi values from 2026-01-01 to 2026-01-31:

2026-01-31: 54.32
2026-01-30: N/A: Not a trading day (weekend or holiday)

RSI: Measures momentum...
```

Rules:

- Reuse existing indicator descriptions where practical.
- Use `stockstats` or existing local indicator utilities after normalizing vnstock OHLCV data.
- Do not make the LLM choose provider-specific indicator names.
- Unsupported indicators shall raise `ValueError` with a list of supported indicator names, matching the existing yfinance behavior.

### 4.6 Fundamental Data Contract

Fundamental functions shall return Markdown plus CSV when a table is available.

`get_fundamentals(ticker, curr_date)` shall combine available company overview and key ratios into a concise report. It should prefer fields such as:

- Company name.
- Exchange.
- Industry or sector.
- Market capitalization.
- Outstanding shares.
- PE ratio.
- PB ratio.
- EPS.
- ROE.
- ROA.
- Dividend yield, if available.

`get_balance_sheet`, `get_cashflow`, and `get_income_statement` shall map `freq="quarterly"` to vnstock's quarterly period parameter and `freq="annual"` to annual or yearly period parameter.

Financial statements shall respect `curr_date` when date or period columns can be parsed. Data after `curr_date` shall be removed to prevent look-ahead bias.

### 4.7 News Data Contract

`get_news(ticker, start_date, end_date)` shall use any news or events capability available in `vnstock`. If the installed `vnstock` version does not support news retrieval, the function shall return a clear message:

```text
No vnstock news data available for FPT between 2026-01-01 and 2026-01-31.
```

`get_global_news(curr_date, look_back_days, limit)` shall return Vietnam market macro headlines if available. If not available through `vnstock`, return a clear message that the vendor does not provide Vietnam macro news rather than falling back internally to US/global yfinance queries. Cross-vendor fallback shall remain the router's responsibility.

`get_insider_transactions(ticker)` shall return Vietnam insider transaction data if a supported `vnstock` API is available. If the adapter does not support insider transaction retrieval, it shall return a clear unsupported-data message such as:

```text
vnstock does not provide insider transaction data through the configured adapter for FPT.
```

### 4.8 Benchmark Return Contract

Update `tradingagents/graph/trading_graph.py` so `_fetch_returns` accepts or reads a configurable benchmark.

Current behavior:

```python
spy = yf.Ticker("SPY").history(start=trade_date, end=end_str)
alpha = raw - spy_ret
```

Required behavior:

- Use `self.config.get("benchmark_symbol", "SPY")`.
- Use `route_to_vendor("get_stock_data", benchmark_symbol, trade_date, end_str)` or a small shared return-fetching helper so benchmark data respects the configured vendor.
- Preserve `SPY` as default for non-Vietnam configurations.
- Use `VNINDEX` for the documented Vietnam config.
- Ensure benchmark labels in reflection output are configurable.

Update `tradingagents/graph/reflection.py` so the human prompt says `Alpha vs <benchmark_label>` rather than `Alpha vs SPY`.

### 4.9 Files To Modify

Required code files:

- `tradingagents/dataflows/vnstock.py`: new adapter module.
- `tradingagents/dataflows/interface.py`: vendor registration, fallback behavior, and explicit Vietnam symbol guard.
- `tradingagents/default_config.py`: market profile, benchmark, currency, vendor option comments, and shared explicit Vietnam symbol helpers.
- `tradingagents/graph/trading_graph.py`: configurable benchmark return calculation and graph-time Vietnam profile application.
- `tradingagents/graph/reflection.py`: configurable benchmark label.
- `tradingagents/agents/utils/agent_utils.py`: Vietnam-aware instrument context examples.
- `tradingagents/agents/utils/core_stock_tools.py`: Vietnam examples in docstrings or annotations.
- `tradingagents/agents/utils/technical_indicators_tools.py`: Vietnam examples in docstrings or annotations.
- `tradingagents/agents/utils/fundamental_data_tools.py`: Vietnam examples in docstrings or annotations.
- `tradingagents/agents/utils/news_data_tools.py`: Vietnam examples and vendor-neutral news wording.
- `cli/utils.py`: ticker prompt examples.
- `cli/main.py`: CLI prompt examples and default text if appropriate.
- `pyproject.toml`: add `vnstock` dependency or optional dependency group.
- `README.md`: document Vietnam setup and example config.
- `main.py`: update sample config or add a commented Vietnam example.

Required test files:

- `tests/test_ticker_symbol_handling.py`: Vietnam symbol preservation and normalization cases.
- `tests/test_memory_log.py`: configurable benchmark behavior replacing hardcoded SPY assumptions.
- `tests/test_vnstock_adapter.py`: new tests for adapter helpers and output formatting.
- `tests/test_data_vendor_routing.py`: new or existing router tests for `vnstock` registration and fallback.

Optional documentation files:

- `CHANGELOG.md`: add an unreleased entry if the project convention requires it.
- `.env.example`: only update if the final implementation needs environment variables. `vnstock` should not require credentials for the initial implementation.

## 5. Acceptance Criteria

- **AC-001**: Given default configuration, when the test suite runs, then existing yfinance and Alpha Vantage behavior remains unchanged.
- **AC-002**: Given `config["data_vendors"]["core_stock_apis"] = "vnstock"`, when `get_stock_data("FPT", "2026-01-01", "2026-01-31")` is invoked with mocked vnstock data, then the result contains canonical OHLCV CSV columns.
- **AC-003**: Given a user input symbol `HOSE:FPT`, when the vnstock adapter normalizes it, then the provider symbol is `FPT`.
- **AC-004**: Given a user input symbol `FPT.HM`, when the vnstock adapter normalizes it, then the provider symbol is `FPT`.
- **AC-005**: Given a non-Vietnam symbol `7203.T`, when CLI normalization runs, then the symbol remains `7203.T`.
- **AC-006**: Given the Vietnam config with `benchmark_symbol = "VNINDEX"`, when memory-log outcome resolution calculates alpha, then it uses `VNINDEX` benchmark data and not `SPY`.
- **AC-007**: Given default config with no benchmark override, when memory-log outcome resolution calculates alpha, then it uses `SPY`, preserving existing behavior.
- **AC-008**: Given `vnstock` is not installed, the configured vendor chain is `"vnstock,yfinance"`, and the ticker is not an explicit Vietnam symbol, when a routed request is made, then the router falls back to yfinance rather than failing during test collection.
- **AC-009**: Given mocked vnstock financial statements containing periods after `curr_date`, when a fundamental statement function is called with `curr_date`, then future periods are excluded.
- **AC-010**: Given `vnstock` does not expose news in the installed version, when `get_news` is called, then the function returns a clear no-data message instead of raising an unhandled exception.
- **AC-011**: Given the market analyst calls `get_indicators` for `rsi`, when the vendor is `vnstock`, then output format is compatible with existing indicator report expectations.
- **AC-012**: Given default yfinance configuration and an explicit Vietnam symbol such as `HOSE:VIC`, when a ticker-scoped data request is routed, then the request uses `vnstock` and does not call yfinance.
- **AC-013**: Given default yfinance configuration and a plain symbol such as `VIC`, when a ticker-scoped data request is routed, then the request follows the configured yfinance path unless the user has explicitly set the Vietnam profile or `vnstock` vendor chain.
- **AC-014**: Given `TradingAgentsGraph.propagate("HOSE:VIC", trade_date)`, when the graph starts, then the graph applies the Vietnam profile, uses `VNINDEX` as the benchmark, and sets ticker-scoped data vendors to `vnstock,yfinance` before pending memory-log outcome resolution.
- **AC-015**: Given `vnstock` does not support insider transactions, when `get_insider_transactions("HOSE:FPT")` is called through the `vnstock` adapter, then it returns a clear unsupported-data message instead of falling through to yfinance.
- **AC-016**: Given a coding agent reads this specification, it can identify all required files, interfaces, and tests without additional repository discovery.

## 6. Test Automation Strategy

- **Test Levels**: Unit tests and focused integration-style tests with mocked provider APIs.
- **Frameworks**: Pytest and unittest patterns already used in the repository.
- **Mocking**: Use `unittest.mock.patch` or pytest monkeypatch to replace `vnstock` imports/classes and provider responses.
- **No Network**: Default tests shall not call real `vnstock`, yfinance, Alpha Vantage, or external news endpoints.
- **Provider Registration Tests**: Assert that `"vnstock"` is present in `VENDOR_LIST` and mapped for the required methods.
- **Symbol Tests**: Assert Vietnam symbol normalization while preserving existing exchange-qualified ticker behavior.
- **Explicit Routing Tests**: Assert that explicit Vietnam symbols route to `vnstock` even when the default vendor config is yfinance, and that plain symbols continue to follow the configured vendor.
- **DataFrame Tests**: Use small Pandas DataFrames to test OHLCV normalization, date filtering, and CSV formatting.
- **Benchmark Tests**: Mock benchmark data and assert `TradingAgentsGraph._fetch_returns` or its replacement uses the configured benchmark symbol.
- **Graph Profile Tests**: Assert that `TradingAgentsGraph.propagate()` or its profile helper applies the Vietnam profile before data fetches for explicit Vietnam symbols.
- **Fallback Tests**: Simulate `DataVendorUnavailableError` from `vnstock` and assert the router continues to the next configured vendor for non-explicit symbols. For explicit Vietnam symbols, assert that the router does not call yfinance as a silent fallback.

Recommended commands:

```bash
uv run pytest tests/test_ticker_symbol_handling.py tests/test_vnstock_adapter.py tests/test_data_vendor_routing.py tests/test_memory_log.py
```

If `uv` is unavailable:

```bash
pytest tests/test_ticker_symbol_handling.py tests/test_vnstock_adapter.py tests/test_data_vendor_routing.py tests/test_memory_log.py
```

## 7. Rationale & Context

TradingAgents currently supports provider routing for yfinance and Alpha Vantage. Vietnamese equities need a Vietnam-native data provider because yfinance symbol coverage, fundamentals, local indices, foreign-flow context, and news are incomplete or inconsistent for Vietnam.

`vnstock` is the recommended first provider because it is Python-native, accessible without paid credentials, and covers the minimum data categories required for the existing TradingAgents workflow. Paid or broker-backed providers such as FiinQuant and SSI FastConnect may be more robust for real-time or institutional workloads, but they introduce onboarding and credential requirements that are not suitable for a first open-source integration.

The main correctness issue outside the data adapter is benchmark alpha. The current memory-log outcome path uses `SPY`, which is not an appropriate benchmark for Vietnam-listed equities. A market-aware benchmark setting fixes this while preserving existing default behavior.

## 8. Dependencies & External Integrations

### External Systems

- **EXT-001**: vnstock upstream public data sources - Provide Vietnam equity, index, financial statement, and related market datasets through the `vnstock` Python package.

### Third-Party Services

- **SVC-001**: vnstock Python package - Required for the `vnstock` vendor adapter at runtime when that vendor is selected.

### Infrastructure Dependencies

- **INF-001**: Local data cache directory - Existing `data_cache_dir` shall continue to be used for provider cache files when caching is added or reused.

### Data Dependencies

- **DAT-001**: Vietnam OHLCV data - Must include enough fields to compute technical indicators.
- **DAT-002**: Vietnam financial statement data - Must include balance sheet, cash flow, and income statement tables when available.
- **DAT-003**: Vietnam benchmark index data - Must include historical close prices for `VNINDEX` or an equivalent configured benchmark.

### Technology Platform Dependencies

- **PLT-001**: Python runtime - Must remain compatible with the repository's supported Python version from `pyproject.toml`.
- **PLT-002**: Pandas - Existing Pandas dependency shall be used for DataFrame normalization and CSV output.
- **PLT-003**: stockstats - Existing stockstats dependency may be reused for local indicator calculations.

### Compliance Dependencies

- **COM-001**: Data provider terms - Documentation shall state that users are responsible for complying with vnstock and upstream data-source terms.
- **COM-002**: Financial advice disclaimer - Documentation shall preserve the repository disclaimer that outputs are for research and not financial advice.

## 9. Examples & Edge Cases

### 9.1 Vietnam Config Example

```python
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

config = DEFAULT_CONFIG.copy()
config["market_profile"] = "vietnam"
config["benchmark_symbol"] = "VNINDEX"
config["currency"] = "VND"
config["data_vendors"] = {
    "core_stock_apis": "vnstock,yfinance",
    "technical_indicators": "vnstock,yfinance",
    "fundamental_data": "vnstock,yfinance",
    "news_data": "vnstock,yfinance",
}

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("FPT", "2026-04-20")
```

### 9.2 Symbol Normalization Examples

| Input       | vnstock provider symbol | Notes                                                                                                           |
| ----------- | ----------------------- | --------------------------------------------------------------------------------------------------------------- |
| `FPT`       | `FPT`                   | Native Vietnam local code.                                                                                      |
| `fpt`       | `FPT`                   | Trim and uppercase.                                                                                             |
| `HOSE:FPT`  | `FPT`                   | Strip known Vietnam exchange prefix.                                                                            |
| `HNX:SHS`   | `SHS`                   | Strip known Vietnam exchange prefix.                                                                            |
| `UPCOM:ABC` | `ABC`                   | Strip known Vietnam exchange prefix.                                                                            |
| `FPT.HM`    | `FPT`                   | yfinance Ho Chi Minh-style suffix maps to local code for vnstock only.                                          |
| `SHS.HN`    | `SHS`                   | yfinance Hanoi-style suffix maps to local code for vnstock only.                                                |
| `7203.T`    | `7203.T`                | Not normalized by CLI or generic code; only vnstock adapter may perform Vietnam-specific mapping when selected. |
| `BRK.B`     | `BRK.B`                 | Must remain preserved for non-Vietnam workflows.                                                                |

### 9.3 Empty Data Example

```text
No data found for symbol 'FAKE' between 2026-01-01 and 2026-01-31
```

### 9.4 Missing Optional Dependency Example

```text
DataVendorUnavailableError: vnstock is not installed. Install vnstock or configure another data vendor.
```

If the configured vendor chain is `"vnstock,yfinance"` and the symbol is not an explicit Vietnam symbol, the router shall catch this error and attempt yfinance.

For explicit Vietnam symbols such as `HOSE:VIC`, the router shall not silently call yfinance after `vnstock` is unavailable because yfinance treats those forms as invalid or delisted. The caller should install the Vietnam extra or choose a different configured workflow deliberately.

### 9.5 Explicit Vietnam Symbol Routing Example

```text
Input symbol: HOSE:VIC
Configured core_stock_apis: yfinance
Effective ticker-scoped vendor: vnstock
Provider symbol: VIC
```

The router-level guard applies even when the configured vendor starts with yfinance. If a graph run starts with `HOSE:VIC`, graph-level profile application also sets the run configuration to the Vietnam profile so later tool calls using either `HOSE:VIC` or plain `VIC` use `vnstock` first.

### 9.6 News Unavailable Example

```text
No vnstock news data available for FPT between 2026-01-01 and 2026-01-31.
```

### 9.7 Insider Transactions Unavailable Example

```text
vnstock does not provide insider transaction data through the configured adapter for FPT.
```

## 10. Validation Criteria

- **VAL-001**: `uv run pytest` or `pytest` passes for the focused tests named in this specification.
- **VAL-002**: Existing ticker preservation tests still pass.
- **VAL-003**: `vnstock` vendor registration is discoverable from `tradingagents/dataflows/interface.py`.
- **VAL-004**: The default config remains non-Vietnam and benchmarked to `SPY`.
- **VAL-005**: The documented Vietnam config routes stock, indicator, fundamental, and news calls to `vnstock` first.
- **VAL-006**: The adapter formats OHLCV and financial statement data as strings consumable by the existing agent tools.
- **VAL-007**: The memory-log reflection prompt uses the configured benchmark label.
- **VAL-008**: Documentation includes at least one runnable Python configuration example for Vietnam equities.
- **VAL-009**: No default test requires real API keys or live network access.
- **VAL-010**: Explicit Vietnam symbols cannot trigger yfinance invalid-symbol or delisted warnings through ticker-scoped routed tool calls.
- **VAL-011**: Programmatic graph runs using explicit Vietnam symbols apply the Vietnam profile before resolving pending memory-log entries.

## 11. Related Specifications / Further Reading

- `AGENTS.md`: Repository-level architecture and coding conventions.
- `README.md`: User setup, data-provider notes, and financial advice disclaimer.
- `tradingagents/dataflows/interface.py`: Existing vendor-router implementation.
- `tradingagents/dataflows/y_finance.py`: Existing yfinance data vendor implementation.
- `tradingagents/dataflows/stockstats_utils.py`: Existing OHLCV loading and indicator support utilities.
- `tests/test_ticker_symbol_handling.py`: Current exchange-qualified ticker preservation tests.
- `tests/test_memory_log.py`: Current memory-log outcome and benchmark tests.
- vnstock public documentation and repository: Use the current stable API at implementation time.
