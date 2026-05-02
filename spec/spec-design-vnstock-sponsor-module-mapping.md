---
title: vnstock Sponsor Module Mapping for TradingAgents Adapter
version: 1.0
date_created: 2026-05-02
last_updated: 2026-05-02
owner: TradingAgents maintainers
tags: [design, vnstock, sponsor, premium, adapter, vietnam]
---

# Introduction

This specification defines how a coding agent shall map the vnstock sponsor ecosystem to the existing TradingAgents adapter in `tradingagents/dataflows/vnstock.py`. The goal is to identify which sponsor module should back each helper and public function, preserve the current router-facing interface, and avoid wiring batch-oriented sponsor packages into synchronous request paths where they do not fit.

## 1. Purpose & Scope

This specification applies to the TradingAgents Python repository and specifically to the Vietnam data adapter in `tradingagents/dataflows/vnstock.py`.

The scope includes:

- Mapping sponsor modules to the exact helper and public functions already defined in `tradingagents/dataflows/vnstock.py`.
- Defining which sponsor modules shall be preferred, which shall remain optional, and which shall not be used on the synchronous request path.
- Preserving the current adapter signatures consumed by `tradingagents/dataflows/interface.py`.
- Defining fallback behavior when sponsor packages are absent or partially available.
- Defining tests and validation criteria for sponsor-aware mapping.

The scope excludes:

- Replacing the vendor router with sponsor-specific routing logic.
- Adding new public router methods beyond the current `vnstock.py` surface.
- Automating sponsor installation from TradingAgents.
- Making sponsor packages mandatory for the default install or default test suite.
- Converting current synchronous adapter methods into background jobs or exported pipelines.

## 2. Definitions

- **TradingAgents adapter**: The module `tradingagents/dataflows/vnstock.py`, which exposes the router-facing functions `get_stock`, `get_indicator`, `get_fundamentals`, `get_balance_sheet`, `get_cashflow`, `get_income_statement`, `get_news`, `get_global_news`, and `get_insider_transactions`.
- **Sponsor module**: A premium vnstock package distributed through the sponsor/member installation flow, such as `vnstock_data`, `vnstock_ta`, `vnstock_news`, or `vnstock_pipeline`.
- **Base vnstock**: The public `vnstock` package currently used by TradingAgents for Vietnam support and optional `VNSTOCK_API_KEY` registration.
- **Synchronous request path**: A direct router call from `route_to_vendor(...)` down to a `vnstock.py` function that is expected to return a string result in the same execution flow.
- **Capability registry**: A small internal helper structure that records whether optional sponsor modules are importable and which objects they expose.
- **Issuer-scoped news**: News tied to a single company or ticker, such as data returned from `Company.news()`.
- **Macro news**: Cross-market or economy-wide headlines that are not tied to one issuer.
- **Batch pipeline**: A multi-ticker, export-oriented, or scheduled workflow such as a `vnstock_pipeline` task.

## 3. Requirements, Constraints & Guidelines

### Functional Requirements

- **REQ-001**: The sponsor-aware implementation shall preserve the current public function signatures in `tradingagents/dataflows/vnstock.py`.
- **REQ-002**: Sponsor module selection shall remain localized to `tradingagents/dataflows/vnstock.py` and shall not require changes to agent prompts, tool wrappers, or router method names.
- **REQ-003**: `vnstock_data` shall be the preferred sponsor module for price-history access used by `_make_quote`, `_quote_history`, `_fetch_ohlcv`, and `get_stock`.
- **REQ-004**: `vnstock_data` shall be the preferred sponsor module for financial statement and ratio access used by `_make_finance`, `_call_finance_table`, `get_fundamentals`, `get_balance_sheet`, `get_cashflow`, and `get_income_statement`.
- **REQ-005**: `vnstock_data` shall be the preferred sponsor module for issuer/company access used by `_make_company`, `_call_company_table`, and `get_insider_transactions`.
- **REQ-006**: `get_news(ticker, start_date, end_date)` shall remain issuer-scoped in the first sponsor-aware pass and shall prefer `vnstock_data.Company.news()` over `vnstock_news`.
- **REQ-007**: `get_global_news(curr_date, look_back_days, limit)` shall prefer `vnstock_news` in the first sponsor-aware pass because it is the sponsor module whose documented purpose matches multi-source market news aggregation.
- **REQ-008**: `get_indicator(symbol, indicator, curr_date, look_back_days)` shall prefer `vnstock_ta.Indicator` when that module is available and the requested indicator has a deterministic translation from the current TradingAgents indicator vocabulary.
- **REQ-009**: When `vnstock_ta` is unavailable or lacks a deterministic translation for a requested indicator, `get_indicator` shall fall back to the current local `stockstats` computation path.
- **REQ-010**: No current routed function in `tradingagents/dataflows/vnstock.py` shall directly invoke `vnstock_pipeline` in the first sponsor-aware pass.
- **REQ-011**: Sponsor module detection shall be optional and lazy. If sponsor packages are absent, the adapter shall continue to function through the current base `vnstock` path where available.
- **REQ-012**: `VNSTOCK_API_KEY` registration shall continue to be handled through base `vnstock` auth initialization. Sponsor module adoption shall not add a second TradingAgents auth flow unless the installed sponsor packages explicitly require one and that requirement is documented in a follow-up spec.
- **REQ-013**: The adapter shall not import installer/support packages such as `vnai`, `vnii`, or `vnstock_installer` at runtime.
- **REQ-014**: Sponsor-aware behavior shall preserve the current string output contracts: Markdown headers plus CSV or concise labeled text.

### Compatibility Requirements

- **CMP-001**: Existing behavior shall remain unchanged when only base `vnstock` is installed.
- **CMP-002**: Existing behavior shall remain unchanged when sponsor packages are installed but a specific sponsor capability is not used by the current method.
- **CMP-003**: Default tests shall continue to run without real sponsor credentials, real network access, or the sponsor installer.
- **CMP-004**: Explicit Vietnam symbol handling, ticker normalization, and current router integration shall remain unchanged.

### Constraints

- **CON-001**: Do not change the router-facing public method names in `tradingagents/dataflows/vnstock.py`.
- **CON-002**: Do not import optional sponsor packages at module import time. Imports shall happen inside lazy helpers.
- **CON-003**: Do not make sponsor packages mandatory dependencies in `pyproject.toml` for the default installation path.
- **CON-004**: Do not use `vnstock_pipeline` inside synchronous request handlers such as `get_stock`, `get_news`, or `get_global_news`.
- **CON-005**: Do not replace issuer-scoped `get_news(ticker, ...)` with a heuristic crawler-only search that lacks deterministic ticker filtering.
- **CON-006**: Do not remove the current base `vnstock` fallback path for price, finance, or company data.
- **CON-007**: Do not add a second environment variable or TradingAgents config key for sponsor-module selection in the first implementation pass.

### Guidelines

- **GUD-001**: Introduce a small capability loader such as `_load_vnstock_capabilities()` or equivalent instead of scattering optional imports across many functions.
- **GUD-002**: Prefer top-level sponsor imports such as `from vnstock_data import Quote, Finance, Company` when those APIs exist in the installed version. Only fall back to deeper module paths when the top-level import is unavailable.
- **GUD-003**: Keep the indicator translation layer explicit and table-driven so the current TradingAgents indicator names remain stable.
- **GUD-004**: Treat `vnstock_news` as a market-news source, not as a generic substitute for all ticker-scoped company-news calls.
- **GUD-005**: Treat `vnstock_pipeline` as an offline or batch utility that may support future cache warming, scheduled downloads, or exported datasets, but not the current router contract.
- **PAT-001**: Prefer a priority order of `sponsor module -> base vnstock -> existing local fallback` when a method has a sensible degradation path.

## 4. Interfaces & Data Contracts

### 4.1 Sponsor Capability Contract

The adapter should use a lazy capability registry that records the availability of sponsor modules without forcing them to be present.

Recommended internal contract:

```python
def _load_vnstock_capabilities() -> dict:
    return {
        "base": _load_vnstock(),
        "data": _optional_import("vnstock_data"),
        "ta": _optional_import("vnstock_ta"),
        "news": _optional_import("vnstock_news"),
        "pipeline": _optional_import("vnstock_pipeline"),
    }
```

Rules:

- `base` is required for the existing adapter path.
- `data`, `ta`, and `news` are optional sponsor capabilities.
- `pipeline` may be discovered for future use, but the current request path shall not call it.
- Missing sponsor modules shall not fail adapter import or test collection.

### 4.2 Helper-Level Mapping Contract

The following table defines the exact sponsor module target for helper functions already present in `tradingagents/dataflows/vnstock.py`.

| Current helper in `vnstock.py`                              | Preferred sponsor module                                                               | Preferred sponsor object/API                                                              | Required fallback                                    | Notes                                                                                         |
| ----------------------------------------------------------- | -------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | ---------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `_load_vnstock()`                                           | base `vnstock` only                                                                    | `register_user`, `Vnstock`, public auth surface                                           | `DataVendorUnavailableError` when base missing       | This helper keeps auth responsibility. It should not become a sponsor-installer wrapper.      |
| New capability loader helper                                | `vnstock_data`, `vnstock_ta`, `vnstock_news`, optional discovery of `vnstock_pipeline` | top-level package imports or documented module imports                                    | return `None` for missing optional packages          | New helper recommended by this spec.                                                          |
| `_make_quote(vnstock_module, symbol)`                       | `vnstock_data`                                                                         | `Quote(symbol=..., source=...)`                                                           | base `vnstock.Quote` or `Vnstock().stock(...).quote` | Quote history remains the correct fit for current OHLCV request shape.                        |
| `_quote_history(quote, symbol, start_date, end_date)`       | `vnstock_data`                                                                         | `Quote.history(...)`                                                                      | same method on base quote object                     | No output contract changes.                                                                   |
| `_fetch_ohlcv(symbol, start_date, end_date)`                | `vnstock_data`                                                                         | composed `Quote.history(...)` path                                                        | current base `vnstock` path                          | This helper should stay sponsor-aware because it feeds stock data and local indicators.       |
| `_make_finance(vnstock_module, symbol)`                     | `vnstock_data`                                                                         | `Finance(symbol=..., source=...)`                                                         | base `vnstock.Finance` or `stock.finance`            | Sponsor data module is the best match for structured finance tables.                          |
| `_call_finance_table(symbol, method_name, freq, curr_date)` | `vnstock_data`                                                                         | `Finance.balance_sheet`, `Finance.cash_flow`, `Finance.income_statement`, `Finance.ratio` | current base finance path                            | Date filtering remains local to TradingAgents.                                                |
| `_make_company(vnstock_module, symbol)`                     | `vnstock_data`                                                                         | `Company(symbol=..., source=...)`                                                         | base `vnstock.Company` or `stock.company`            | Company-scoped methods remain the safest mapping for overview, issuer news, and insider data. |
| `_call_company_table(symbol, method_name)`                  | `vnstock_data`                                                                         | `Company.overview`, `Company.news`, `Company.insider_trading`                             | current base company path                            | Company methods should stay thin wrappers around provider data.                               |
| New TA helper, if added                                     | `vnstock_ta`                                                                           | `Indicator(data)`                                                                         | current `stockstats.wrap(data)` path                 | Needed so `get_indicator` can use sponsor TA without changing public signatures.              |
| New global-news helper, if added                            | `vnstock_news`                                                                         | `list_supported_sites`, `Crawler`, `AsyncBatchCrawler` or equivalent documented surface   | current clear no-data message                        | Keep this helper isolated so crawler complexity does not leak into company-data helpers.      |

### 4.3 Public Function Mapping Contract

The following table defines the exact sponsor module target for each router-facing function in `tradingagents/dataflows/vnstock.py`.

| Public function in `vnstock.py`                               | Primary sponsor module | Primary sponsor API family                       | Required fallback path                                   | Mapping decision                                                                                                            |
| ------------------------------------------------------------- | ---------------------- | ------------------------------------------------ | -------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `get_stock(symbol, start_date, end_date)`                     | `vnstock_data`         | `Quote.history(...)`                             | current base `vnstock` quote path                        | Use sponsor data module because it matches structured OHLCV retrieval and higher-limit quote access.                        |
| `get_indicator(symbol, indicator, curr_date, look_back_days)` | `vnstock_ta`           | `Indicator(data)` plus explicit name translation | current local `stockstats` path over `_fetch_ohlcv(...)` | Use sponsor TA only for indicator calculation. Fetching OHLCV remains the responsibility of the quote path.                 |
| `get_fundamentals(ticker, curr_date)`                         | `vnstock_data`         | `Company.overview()` plus `Finance.ratio(...)`   | current base company/finance path                        | Sponsor data module is the correct structured-data source for overview and ratios.                                          |
| `get_balance_sheet(ticker, freq, curr_date)`                  | `vnstock_data`         | `Finance.balance_sheet(...)`                     | current base finance path                                | Direct table mapping.                                                                                                       |
| `get_cashflow(ticker, freq, curr_date)`                       | `vnstock_data`         | `Finance.cash_flow(...)`                         | current base finance path                                | Direct table mapping.                                                                                                       |
| `get_income_statement(ticker, freq, curr_date)`               | `vnstock_data`         | `Finance.income_statement(...)`                  | current base finance path                                | Direct table mapping.                                                                                                       |
| `get_news(ticker, start_date, end_date)`                      | `vnstock_data`         | `Company.news()`                                 | current base company path                                | In the first sponsor-aware pass, keep this issuer-scoped and do not replace it with crawler heuristics from `vnstock_news`. |
| `get_global_news(curr_date, look_back_days, limit)`           | `vnstock_news`         | crawler or site-list-based market news retrieval | current clear unavailable message                        | This is the only current router-facing function that should directly target the sponsor news module in the first pass.      |
| `get_insider_transactions(ticker)`                            | `vnstock_data`         | `Company.insider_trading()`                      | current base company path                                | Sponsor data module is the correct structured company-data source.                                                          |

### 4.4 Indicator Translation Contract

`get_indicator(...)` already exposes a stable TradingAgents vocabulary. Sponsor TA adoption shall preserve that vocabulary through an adapter-owned translation table.

Recommended translation contract:

```python
SPONSOR_TA_MAPPING = {
    "close_50_sma": {"method": "sma", "kwargs": {"length": 50}},
    "close_200_sma": {"method": "sma", "kwargs": {"length": 200}},
    "close_10_ema": {"method": "ema", "kwargs": {"length": 10}},
    "macd": {"method": "macd", "kwargs": {"fast": 12, "slow": 26, "signal": 9}},
    "macds": {"method": "macd", "kwargs": {"fast": 12, "slow": 26, "signal": 9}},
    "macdh": {"method": "macd", "kwargs": {"fast": 12, "slow": 26, "signal": 9}},
    "rsi": {"method": "rsi", "kwargs": {"length": 14}},
    "boll": {"method": "bbands", "kwargs": {"length": 20, "std": 2}},
    "boll_ub": {"method": "bbands", "kwargs": {"length": 20, "std": 2}},
    "boll_lb": {"method": "bbands", "kwargs": {"length": 20, "std": 2}},
    "atr": {"method": "atr", "kwargs": {"length": 14}},
    "vwma": {"method": "vwma", "kwargs": {"length": 20}},
    "mfi": {"method": "mfi", "kwargs": {"length": 14}},
}
```

Rules:

- The translation table shall live in `tradingagents/dataflows/vnstock.py` or a nearby helper module.
- The coding agent shall verify exact sponsor TA method names against the installed version before implementation.
- `macd`, `macds`, and `macdh` may originate from one sponsor call and then be mapped back to the current single-series output shape expected by TradingAgents.
- `boll`, `boll_ub`, and `boll_lb` may originate from one sponsor Bollinger call and then be mapped back to the existing TradingAgents names.
- When a sponsor result shape cannot be deterministically projected back to the current output, the adapter shall fall back to the current `stockstats` logic.

### 4.5 Explicit Non-Mapping Contract for `vnstock_pipeline`

`vnstock_pipeline` shall have no direct mapping to any current router-facing function in `tradingagents/dataflows/vnstock.py`.

Rationale:

- The documented `vnstock_pipeline` APIs are batch-oriented and operate on multiple tickers, scheduled jobs, exported files, or long-running tasks.
- The current TradingAgents router expects synchronous string-returning functions.
- Forcing `vnstock_pipeline` into `get_stock`, `get_news`, or `get_global_news` would add export/scheduler concerns to request handlers.

Permitted future use:

- Optional cache warmers.
- Offline dataset preparation under `scripts/` or a separate ingestion module.
- Benchmark data backfills outside the router request path.

Forbidden first-pass use:

- Calling `run_task`, `run_intraday_task`, `run_financial_task`, or `run_price_board` directly inside current `vnstock.py` public functions.

### 4.6 Files To Modify For Implementation

Required implementation files:

- `tradingagents/dataflows/vnstock.py`
- `tests/test_vnstock_adapter.py`

Likely supporting files:

- `README.md`
- `pyproject.toml` if sponsor guidance or optional extras documentation is updated

## 5. Acceptance Criteria

- **AC-001**: Given only base `vnstock` is installed, when a TradingAgents router call reaches any current public function in `tradingagents/dataflows/vnstock.py`, then behavior remains consistent with the pre-sponsor implementation.
- **AC-002**: Given `vnstock_data` is installed, when `get_stock("FPT", start, end)` is called, then the adapter resolves quote/history through sponsor data helpers rather than the base fallback path.
- **AC-003**: Given `vnstock_data` is installed, when `get_fundamentals`, `get_balance_sheet`, `get_cashflow`, `get_income_statement`, or `get_insider_transactions` is called, then the adapter resolves the underlying provider object through sponsor `Company` and `Finance` surfaces.
- **AC-004**: Given `vnstock_ta` is installed and the requested indicator is supported by the translation table, when `get_indicator(...)` is called, then the adapter computes the indicator through `vnstock_ta.Indicator` and still returns the current TradingAgents output format.
- **AC-005**: Given `vnstock_ta` is absent or the requested indicator lacks a deterministic sponsor mapping, when `get_indicator(...)` is called, then the adapter falls back to the existing `stockstats` path instead of failing.
- **AC-006**: Given `vnstock_news` is installed, when `get_global_news(...)` is called, then the adapter uses the sponsor news module rather than returning the current fixed unavailable message.
- **AC-007**: Given `vnstock_news` is installed, when `get_news(ticker, start_date, end_date)` is called, then the adapter still prefers issuer-scoped company news and does not replace that method with an undifferentiated site crawl.
- **AC-008**: Given `vnstock_pipeline` is installed, when any current router-facing function in `tradingagents/dataflows/vnstock.py` is called, then no pipeline task function is imported or invoked on the synchronous request path.
- **AC-009**: Given sponsor installer-support packages are present or absent, when TradingAgents imports `tradingagents/dataflows/vnstock.py`, then the adapter does not import `vnai`, `vnii`, or `vnstock_installer`.
- **AC-010**: Given `VNSTOCK_API_KEY` is set, when sponsor-aware adapter methods are exercised, then auth initialization still flows through base `vnstock` registration and no second TradingAgents auth mechanism is required.

## 6. Test Automation Strategy

- **Test Levels**: Unit tests with mocked imports and mocked sponsor/base provider objects.
- **Frameworks**: Pytest with `unittest.mock.patch` or pytest monkeypatch.
- **Test Data Management**: Use small in-memory Pandas DataFrames for OHLCV, finance, company news, and insider tables.
- **Import Simulation**: Patch `importlib`-style helper functions or adapter-local lazy import helpers to emulate installed and missing sponsor packages.
- **No Network**: Tests shall not hit real sponsor services, real crawlers, or real `vnstock` endpoints.
- **Coverage Focus**:
  - Sponsor-data preference for quote, finance, and company helpers.
  - TA preference and local fallback for `get_indicator`.
  - News-module preference only for `get_global_news`.
  - Explicit non-use of `vnstock_pipeline` on current request paths.
  - Preservation of output formatting and symbol normalization.
- **CI/CD Integration**: Add focused tests to the existing suite so sponsor-aware mapping is validated without requiring sponsor installation.

Recommended test cases:

- `test_sponsor_quote_mapping_prefers_vnstock_data()`
- `test_sponsor_finance_mapping_prefers_vnstock_data()`
- `test_sponsor_company_mapping_prefers_vnstock_data_for_insider_transactions()`
- `test_get_indicator_prefers_vnstock_ta_when_available()`
- `test_get_indicator_falls_back_to_stockstats_when_ta_missing()`
- `test_get_news_stays_company_scoped_even_when_vnstock_news_is_installed()`
- `test_get_global_news_uses_vnstock_news_when_available()`
- `test_pipeline_not_used_by_current_request_handlers()`

## 7. Rationale & Context

The sponsor ecosystem is split by capability rather than by one drop-in replacement package for every current TradingAgents function.

- `vnstock_data` is the closest fit for the current adapter because TradingAgents already needs structured quote, company, and finance objects.
- `vnstock_ta` is a focused technical-analysis layer and should only replace indicator computation, not the quote-loading path.
- `vnstock_news` is documented as a multi-source news crawler and therefore fits `get_global_news` better than issuer-scoped `get_news(ticker, ...)`.
- `vnstock_pipeline` is a batch and export layer. Its shape conflicts with the current router contract, which expects immediate string results.

This split minimizes implementation risk. It improves sponsor usage where the sponsor modules match the existing TradingAgents abstractions and explicitly rejects mappings that would force background-job semantics into request handlers.

## 8. Dependencies & External Integrations

### External Systems

- **EXT-001**: Base `vnstock` package - Provides current auth registration and public Vietnam data APIs.
- **EXT-002**: `vnstock_data` sponsor package - Provides higher-limit structured quote, company, and finance APIs.
- **EXT-003**: `vnstock_ta` sponsor package - Provides sponsor technical-indicator calculation APIs.
- **EXT-004**: `vnstock_news` sponsor package - Provides multi-source news crawling and aggregation APIs.
- **EXT-005**: `vnstock_pipeline` sponsor package - Provides batch and scheduled data ingestion APIs for future offline workflows.

### Third-Party Services

- **SVC-001**: vnstock/vnstocks sponsor distribution service - Provides sponsor package installation and account-scoped entitlement outside TradingAgents.

### Infrastructure Dependencies

- **INF-001**: Python runtime with optional-import support - Needed so sponsor packages can remain optional.
- **INF-002**: Existing TradingAgents virtual environment - The adapter shall run whether sponsor packages are absent or present.

### Data Dependencies

- **DAT-001**: Sponsor quote history data - Needed for premium OHLCV paths.
- **DAT-002**: Sponsor finance and company tables - Needed for premium fundamentals and insider mappings.
- **DAT-003**: Sponsor news crawler sources - Needed only for `get_global_news` in the first pass.

### Technology Platform Dependencies

- **PLT-001**: Pandas - Needed to normalize sponsor and base data into current string contracts.
- **PLT-002**: stockstats - Retained as the local fallback path for unsupported or unavailable sponsor TA cases.

### Compliance Dependencies

- **COM-001**: Sponsor/member terms - Users remain responsible for complying with vnstock sponsor terms, license, and device restrictions.
- **COM-002**: Research disclaimer - TradingAgents remains a research framework and not financial advice.

## 9. Examples & Edge Cases

### 9.1 Preferred Sponsor Mapping Example

```python
def get_stock(symbol: str, start_date: str, end_date: str) -> str:
    capabilities = _load_vnstock_capabilities()
    data_module = capabilities["data"]
    if data_module is not None:
        quote = data_module.Quote(symbol=_normalize_vietnam_symbol(symbol), source="VCI")
        data = quote.history(start=start_date, end=end_date, interval="1D")
    else:
        data = _fetch_ohlcv_via_base_vnstock(symbol, start_date, end_date)
    return _format_csv_report(...)
```

### 9.2 TA Translation Example

```python
def _compute_indicator_with_sponsor_ta(data: pd.DataFrame, indicator: str) -> pd.Series:
    ta = Indicator(data)
    mapping = SPONSOR_TA_MAPPING[indicator]
    result = getattr(ta, mapping["method"])(**mapping["kwargs"])
    return project_back_to_tradingagents_series(result, indicator)
```

### 9.3 Issuer News Edge Case

```python
# Correct first-pass mapping
get_news("FPT", "2026-04-01", "2026-04-30")
# Uses vnstock_data.Company.news() when sponsor data is available.

# Not permitted in the first pass
# Replacing issuer-scoped news with a site crawl that merely searches article text for "FPT".
```

### 9.4 Global News Edge Case

```python
get_global_news("2026-05-02", look_back_days=7, limit=10)
# Preferred: vnstock_news crawler/site aggregation
# Fallback: current clear unavailable message if sponsor news is absent
```

### 9.5 Pipeline Non-Example

```python
# Forbidden first-pass pattern
def get_stock(symbol, start_date, end_date):
    from vnstock_pipeline.tasks.ohlcv import run_task
    run_task([symbol], start=start_date, end=end_date, interval="1D")
    ...
```

Why forbidden:

- It turns a synchronous request into a batch export job.
- It complicates tests and runtime semantics.
- It does not match the current `str` return contract.

## 10. Validation Criteria

- **VAL-001**: Every current public function in `tradingagents/dataflows/vnstock.py` has an explicit sponsor-module mapping or an explicit no-mapping decision.
- **VAL-002**: The spec clearly distinguishes which functions should use `vnstock_data`, which should use `vnstock_ta`, which should use `vnstock_news`, and which should not use `vnstock_pipeline`.
- **VAL-003**: The spec preserves base `vnstock` as a valid fallback path.
- **VAL-004**: The spec preserves current output contracts and current router-facing function names.
- **VAL-005**: The spec defines a deterministic approach for indicator translation rather than exposing sponsor-specific indicator names to TradingAgents callers.
- **VAL-006**: The spec states that `get_news(ticker, ...)` remains issuer-scoped and that `get_global_news(...)` is the first sponsor-aware news target.
- **VAL-007**: The spec explicitly excludes installer packages and batch pipeline tasks from the current runtime request path.

## 11. Related Specifications / Further Reading

- `spec/spec-data-vietnam-vnstock-support.md`
- `tradingagents/dataflows/vnstock.py`
- vnstock sponsor overview: `https://vnstocks.com/docs/vnstock-insider-api/index`
- vnstock sponsor CLI installation: `https://vnstocks.com/onboard-member/cai-dat-go-loi/cai-dat-nang-cao`
- vnstock public package documentation: `https://github.com/thinh-vu/vnstock`
