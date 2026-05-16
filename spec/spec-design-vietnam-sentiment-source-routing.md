---
title: Vietnam Sentiment Source Routing for TradingAgents
version: 1.0
date_created: 2026-05-16
last_updated: 2026-05-16
owner: TradingAgents maintainers
tags: [design, vietnam, sentiment, news, dataflows, agents]
---

# Introduction

This specification defines the immediate implementation for replacing StockTwits and default United States Reddit sentiment sources when TradingAgents analyzes explicit Vietnam-listed symbols. The goal is to prevent expected `404` and `403` warnings from US-centric social endpoints and to provide Vietnam-relevant news and sentiment context for symbols such as `HOSE:GVR`, `GVR.HM`, `HNX:SHS`, and `VNINDEX`.

## 1. Purpose & Scope

This specification applies to the TradingAgents Python repository, specifically the sentiment analyst and dataflow code used by `tradingagents/agents/analysts/sentiment_analyst.py`.

The scope includes:

- Detecting explicit Vietnam symbols before the sentiment analyst fetches external social data.
- Skipping StockTwits and the default US Reddit subreddits for explicit Vietnam symbols.
- Introducing a Vietnam-specific sentiment/news dataflow helper that returns prompt-ready text blocks.
- Reusing the existing vendor-routed company news path for issuer-scoped Vietnam news.
- Adding low-risk Vietnam news sources that are public, text-based, and practical to parse.
- Keeping noisy forum-style sources optional and clearly labeled.
- Updating sentiment analyst prompt labels so the model understands Vietnam-specific source limitations.
- Adding focused unit tests that do not require real network access, credentials, or optional sponsor packages.
- Updating user-facing documentation where it describes sentiment inputs for Vietnam symbols.

The scope excludes:

- Building a full historical news database.
- Training or shipping a Vietnamese financial sentiment model.
- Adding paid data providers such as FiinGroup, WiFeed, EODHD, or commercial Vietstock data products.
- Scraping private or semi-private communities such as Zalo, Facebook groups, Telegram groups, or authenticated broker chats.
- Making `vnstock_news`, Firecrawl, browser automation, or any paid scraping service mandatory.
- Replacing the broader news analyst or vendor router architecture.
- Adding high-frequency social streaming.

## 2. Definitions

- **TradingAgents**: The multi-agent trading research framework in this repository.
- **Sentiment analyst**: The agent node created by `create_sentiment_analyst(llm)`, currently responsible for combining news, StockTwits, and Reddit content into a sentiment report.
- **Explicit Vietnam symbol**: A ticker form that unambiguously identifies the Vietnam market, as defined by `tradingagents.default_config.is_explicit_vietnam_symbol`. Examples include `HOSE:GVR`, `HNX:SHS`, `UPCOM:ABC`, `GVR.HM`, `SHS.HN`, `VNINDEX`, and `VN30`.
- **Provider symbol**: The local Vietnam symbol used by Vietnam data providers and web pages after removing exchange qualifiers and Vietnam suffixes. Examples: `HOSE:GVR` -> `GVR`, `GVR.HM` -> `GVR`.
- **US social sources**: The current StockTwits symbol stream and Reddit searches over `r/wallstreetbets`, `r/stocks`, and `r/investing`.
- **Vietnam sentiment stack**: The Vietnam-specific replacement source set composed of issuer-scoped news, local financial news, and optional forum-style retail discussion.
- **Issuer-scoped news**: News or disclosures tied to one listed company or ticker.
- **Macro or market-context news**: News about Vietnam equities, sectors, policy, liquidity, foreign flows, or market-wide events that may affect the target ticker but is not necessarily issuer-specific.
- **Forum-style sentiment**: Public investor discussion from a forum or community source. In this first pass, F319 public RSS is the only recommended Vietnam-native candidate.
- **Prompt-ready block**: A plain string returned by a dataflow helper that can be injected into an LLM prompt without further transformation.

## 3. Requirements, Constraints & Guidelines

### Functional Requirements

- **REQ-001**: The sentiment analyst shall detect explicit Vietnam symbols before calling StockTwits or Reddit fetchers.
- **REQ-002**: For explicit Vietnam symbols, the sentiment analyst shall not call `fetch_stocktwits_messages(...)`.
- **REQ-003**: For explicit Vietnam symbols, the sentiment analyst shall not call `fetch_reddit_posts(...)` with the default US subreddit list.
- **REQ-004**: For explicit Vietnam symbols, the sentiment analyst shall call a Vietnam-specific dataflow helper instead of the US social fetchers.
- **REQ-005**: The Vietnam-specific helper shall return prompt-ready text and shall not raise network or parsing exceptions to the sentiment analyst.
- **REQ-006**: The Vietnam-specific helper shall preserve the original user-facing ticker in labels while using a provider symbol for Vietnam URLs and source filtering.
- **REQ-007**: The Vietnam-specific helper shall include issuer-scoped company news from the existing routed news tool where available.
- **REQ-008**: The Vietnam-specific helper shall include at least one public Vietnam local news source in the first implementation pass.
- **REQ-009**: The first implementation pass shall prefer sources that are public and text-based: DNSE Senses ticker news pages and CafeF RSS feeds.
- **REQ-010**: VietstockFinance ticker pages may be included when accessible, but HTTP `403`, redirects, or parse failures shall be reported as source-unavailable placeholders instead of warnings that imply agent failure.
- **REQ-011**: F319 public forum RSS may be included as an optional source, disabled by default unless the implementation adds an explicit config or helper parameter to enable forum ingestion.
- **REQ-012**: Each Vietnam source block shall identify the source name, the target ticker/provider symbol, the time window where available, and whether the content is issuer-scoped, market-context, or forum-style.
- **REQ-013**: If no Vietnam source returns items, the helper shall return a clear no-data message for each attempted source category.
- **REQ-014**: The sentiment analyst prompt shall avoid labeling Vietnam replacement sources as StockTwits or Reddit.
- **REQ-015**: The sentiment analyst prompt shall instruct the model to treat Vietnam forum data as noisy, optional, and lower confidence than formal news and disclosures.
- **REQ-016**: Non-Vietnam workflows shall continue to use existing StockTwits and Reddit behavior.
- **REQ-017**: Plain local symbols such as `GVR` shall remain configuration-driven. They shall not automatically use the Vietnam sentiment stack unless they are treated as Vietnam symbols by an explicit market profile decision in a later implementation.
- **REQ-018**: The implementation shall add unit tests for explicit Vietnam routing, non-Vietnam routing, placeholder behavior, and prompt label changes.

### Compatibility Requirements

- **CMP-001**: Existing `AAPL`, `NVDA`, and other non-Vietnam sentiment runs shall keep the current three-source behavior: news, StockTwits, and Reddit.
- **CMP-002**: Existing Vietnam vendor routing through `vnstock` shall remain unchanged.
- **CMP-003**: The new Vietnam sentiment helper shall not require `vnstock_news` to be installed.
- **CMP-004**: The default test suite shall not perform live HTTP requests to CafeF, DNSE, Vietstock, F319, StockTwits, Reddit, or vnstock.
- **CMP-005**: The implementation shall not introduce a mandatory dependency beyond the current default dependencies unless the dependency is explicitly justified and tested.

### Constraints

- **CON-001**: Do not scrape private, authenticated, or semi-private social communities by default.
- **CON-002**: Do not add Zalo, Facebook groups, Telegram groups, broker chat rooms, TikTok, or YouTube as automated default sources.
- **CON-003**: Do not call StockTwits with Vietnam provider symbols as a fallback. StockTwits does not provide reliable symbol streams for Vietnam-listed equities.
- **CON-004**: Do not call default US Reddit subreddits for explicit Vietnam symbols.
- **CON-005**: Do not hardcode Vietnam source fetching inside the prompt construction block. Keep external fetching in dataflow/helper functions.
- **CON-006**: Do not make network failures visible as Python exceptions to graph execution. Return clear placeholders and use low-noise logging.
- **CON-007**: Do not emit warning-level logs for expected unavailable Vietnam replacement sources unless all configured Vietnam sources fail unexpectedly.
- **CON-008**: Do not change the public ticker-preservation behavior required by Vietnam market data support.

### Guidelines

- **GUD-001**: Place the Vietnam-specific source fetching code in a new module such as `tradingagents/dataflows/vietnam_sentiment.py`.
- **GUD-002**: Use the existing `requests` and `parsel` dependencies, plus Python standard-library XML parsing when practical, before adding a new RSS dependency.
- **GUD-003**: Keep source fetchers small, deterministic, timeout-bound, and independently testable.
- **GUD-004**: Keep the first implementation synchronous because the current sentiment analyst fetch path is synchronous.
- **GUD-005**: Prefer source-specific item limits over large page fetches.
- **GUD-006**: Use polite request headers, short timeouts, and caching-compatible helper boundaries.
- **GUD-007**: Prefer source labels over overconfident sentiment scoring. The LLM can classify source text in the first pass.
- **GUD-008**: If the project later adds a persistent ingestion layer, this helper should become a thin reader over that cache instead of repeatedly fetching the web.
- **PAT-001**: Follow the existing project pattern of returning strings from dataflow helpers so agent code receives uniform prompt-ready text.

## 4. Interfaces & Data Contracts

### 4.1 Sentiment Analyst Routing Contract

The sentiment analyst shall route source collection by ticker market.

Required behavior:

```python
from tradingagents.default_config import is_explicit_vietnam_symbol
from tradingagents.dataflows.vietnam_sentiment import fetch_vietnam_sentiment_sources

if is_explicit_vietnam_symbol(ticker):
    news_block = get_news.func(ticker, start_date, end_date)
    vietnam_sources_block = fetch_vietnam_sentiment_sources(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
    )
    system_message = _build_vietnam_system_message(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        news_block=news_block,
        vietnam_sources_block=vietnam_sources_block,
    )
else:
    news_block = get_news.func(ticker, start_date, end_date)
    stocktwits_block = fetch_stocktwits_messages(ticker, limit=30)
    reddit_block = fetch_reddit_posts(ticker)
    system_message = _build_system_message(...)
```

Equivalent refactoring is allowed if it preserves behavior and testability.

### 4.2 Vietnam Sentiment Helper Contract

Recommended public function:

```python
def fetch_vietnam_sentiment_sources(
    ticker: str,
    start_date: str,
    end_date: str,
    *,
    include_forums: bool = False,
    limit_per_source: int = 8,
    timeout: float = 10.0,
) -> str:
    """Return prompt-ready Vietnam news and sentiment source blocks."""
```

Function rules:

- `ticker` shall be the user-facing ticker from agent state.
- `start_date` and `end_date` shall use `YYYY-MM-DD` format.
- `include_forums` shall default to `False`.
- `limit_per_source` shall cap each source independently.
- `timeout` shall apply to each HTTP request.
- The return value shall always be a string.
- Expected unavailable sources shall appear as placeholders inside the string.
- Unexpected implementation errors may be logged, but shall not stop graph execution.

### 4.3 Provider Symbol Normalization Contract

The helper shall normalize explicit Vietnam symbols to provider symbols for URLs and text matching.

Required examples:

| Input ticker | Provider symbol |
| ------------ | --------------- |
| `HOSE:GVR`   | `GVR`           |
| `HSX:GVR`    | `GVR`           |
| `HNX:SHS`    | `SHS`           |
| `UPCOM:ABC`  | `ABC`           |
| `GVR.HM`     | `GVR`           |
| `SHS.HN`     | `SHS`           |
| `ABC.UPCOM`  | `ABC`           |
| `VNINDEX`    | `VNINDEX`       |
| `VN30`       | `VN30`          |

The helper shall not reuse a private function from `tradingagents/dataflows/vnstock.py` unless that function is intentionally promoted to a shared public utility.

### 4.4 Source Contract

The first implementation pass shall support the following source categories.

| Source category            | Source                                                                       | Required by first pass | Access mode                    | Default enabled  | Notes                                                                                        |
| -------------------------- | ---------------------------------------------------------------------------- | ---------------------- | ------------------------------ | ---------------- | -------------------------------------------------------------------------------------------- |
| Issuer-scoped company news | Existing `get_news.func(ticker, start_date, end_date)`                       | Yes                    | Existing vendor router         | Yes              | Usually routes to `vnstock` for explicit Vietnam symbols.                                    |
| Ticker page news           | DNSE Senses `https://www.dnse.com.vn/senses/co-phieu-{SYMBOL}/tin-tuc`       | Yes                    | Public HTML                    | Yes              | Verified to expose GVR ticker news.                                                          |
| Local financial RSS        | CafeF stock, company, smart-money, and macro RSS feeds                       | Yes                    | Public RSS                     | Yes              | Requires ticker and company-name matching. Ticker-only matching is acceptable in first pass. |
| Ticker page news           | VietstockFinance `https://finance.vietstock.vn/{SYMBOL}/latest-news.htm`     | Optional               | Public HTML, sometimes guarded | Yes if robust    | Must tolerate `403` or redirects gracefully.                                                 |
| Forum-style sentiment      | F319 public RSS `https://f319.com/forums/thi-truong-chung-khoan.3/index.rss` | Optional               | Public RSS                     | No               | Noisy. Enable only by explicit parameter or config.                                          |
| Macro context              | VnEconomy, Vietstock RSS, Stockbiz, VnBusiness, BNews                        | Optional               | Public RSS                     | No in first pass | Suitable for a later macro sentiment expansion.                                              |

### 4.5 Prompt Block Contract

The Vietnam helper shall return a block with stable section headers.

Recommended format:

```text
Vietnam sentiment and news sources for GVR.HM (provider symbol: GVR)
Window: 2026-05-09 to 2026-05-16

## Issuer and company news
<items or unavailable/no-data placeholder>

## Local financial news
Source: DNSE Senses
- [2026-05-15] Title ...

Source: CafeF RSS
- [2026-05-14] Title ...

## Forum-style investor discussion
<disabled by default>
```

Each item should include as many of the following fields as the source provides:

- Publication date or relative date.
- Source name.
- Title.
- Short excerpt or description.
- URL.
- Matched symbol or match reason.

### 4.6 Prompt Construction Contract

The Vietnam sentiment system message shall use Vietnam-specific source labels.

Required sections:

- `News headlines and company disclosures`.
- `Vietnam local market news`.
- `Vietnam investor forum discussion`, only when present or explicitly disabled as a source note.
- `Data limits`, explaining that Vietnam social data is less standardized than StockTwits and Reddit.

The prompt shall not include `StockTwits messages` or `Reddit posts` headings for explicit Vietnam symbols.

## 5. Acceptance Criteria

- **AC-001**: Given ticker `GVR.HM`, when `sentiment_analyst_node` collects sources, then it shall call the Vietnam sentiment helper and shall not call StockTwits or Reddit fetchers.
- **AC-002**: Given ticker `HOSE:GVR`, when `sentiment_analyst_node` collects sources, then it shall call the Vietnam sentiment helper and shall preserve `HOSE:GVR` in user-facing prompt text.
- **AC-003**: Given ticker `AAPL`, when `sentiment_analyst_node` collects sources, then it shall continue calling StockTwits and Reddit fetchers.
- **AC-004**: Given a DNSE Senses HTML response containing ticker news, when the DNSE source parser runs, then it shall return prompt-ready item lines containing titles and URLs.
- **AC-005**: Given a CafeF RSS response containing an item title with the provider symbol, when the CafeF source parser runs, then it shall include that item in the local financial news block.
- **AC-006**: Given a source returns HTTP `403`, `404`, timeout, invalid XML, or unexpected HTML, when the Vietnam helper runs, then it shall return an unavailable placeholder and continue collecting other sources.
- **AC-007**: Given `include_forums=False`, when the Vietnam helper runs, then it shall not fetch F319 RSS and shall include either no forum section or a disabled-source note.
- **AC-008**: Given `include_forums=True`, when F319 RSS contains a post title or excerpt matching the provider symbol, then the helper shall include it in a forum-style source section.
- **AC-009**: Given all Vietnam replacement sources return no matching items, when the helper completes, then the sentiment analyst prompt shall still contain clear no-data placeholders and graph execution shall continue.
- **AC-010**: Given an explicit Vietnam symbol, when the system message is built, then it shall not contain the headings `StockTwits messages` or `Reddit posts`.

## 6. Test Automation Strategy

- **Test Levels**: Unit tests for routing and parsing; optional integration tests for live source availability outside the default suite.
- **Frameworks**: `pytest`, monkeypatching, and in-memory sample HTML/RSS fixtures.
- **Test Data Management**: Store small sample payload strings inside test modules or fixtures. Do not fetch live websites in unit tests.
- **CI/CD Integration**: All default tests shall run without network access and without real credentials.
- **Coverage Requirements**: Cover explicit Vietnam routing, non-Vietnam routing, source normalization, source parser success, source parser no-match, source parser unavailable, and prompt label selection.
- **Performance Testing**: Unit tests shall not sleep. HTTP delay or rate-limit behavior shall be injectable and disabled in tests.

Recommended test files:

- `tests/test_vietnam_sentiment_sources.py`
- `tests/test_sentiment_analyst_routing.py`

Recommended mocked functions:

- `fetch_stocktwits_messages`
- `fetch_reddit_posts`
- `fetch_vietnam_sentiment_sources`
- HTTP request helper inside `tradingagents/dataflows/vietnam_sentiment.py`

## 7. Rationale & Context

StockTwits returns `404 Not Found` for Vietnam-listed symbols such as `GVR.HM` and bare `GVR`. Reddit public JSON search currently returns `403 Blocked` from the tested environment even for common US tickers. These failures are provider behavior, not evidence that Vietnam market-data routing is broken.

The existing Vietnam market profile correctly routes market data and company news toward `vnstock`, but the sentiment analyst fetches StockTwits and Reddit unconditionally. This creates noisy warnings and gives the model source labels that do not match Vietnam-listed equities.

The immediate implementation shall solve that mismatch by making source selection market-aware. It shall avoid broad scraping, paid integrations, and private social communities in the first pass. The replacement stack prioritizes reliable formal and semi-formal sources before noisy forum data because Vietnam retail discussion is fragmented across platforms that are not clean public APIs.

## 8. Dependencies & External Integrations

### External Systems

- **EXT-001**: DNSE Senses - Public ticker news pages for Vietnam equities. Used for ticker-scoped local news cards.
- **EXT-002**: CafeF RSS - Public RSS feeds for Vietnamese financial, company, stock-market, smart-money, and macro news.
- **EXT-003**: VietstockFinance - Public ticker pages for company news and disclosures. Used opportunistically when accessible.
- **EXT-004**: F319 - Public forum RSS for Vietnam investor discussion. Optional and disabled by default in the first pass.

### Third-Party Services

- **SVC-001**: No paid third-party service shall be required for the first implementation pass.
- **SVC-002**: `vnstock_news` may be used by existing Vietnam news paths when installed, but it shall not be mandatory for this spec.

### Infrastructure Dependencies

- **INF-001**: Internet access is required only for live runs that enable web source fetching. Unit tests shall not require internet access.
- **INF-002**: Source fetchers shall support short request timeouts to prevent sentiment analysis from hanging on external websites.

### Data Dependencies

- **DAT-001**: Vietnam ticker symbol normalization shall support explicit Vietnam forms already recognized by `is_explicit_vietnam_symbol`.
- **DAT-002**: Source item matching shall support exact provider-symbol matching in titles, descriptions, or visible ticker tags.
- **DAT-003**: Future company-name matching may use vnstock or exchange symbol metadata, but it is not required for the immediate first pass.

### Technology Platform Dependencies

- **PLT-001**: Python 3.10 or newer, matching the project requirement.
- **PLT-002**: Existing default dependencies `requests` and `parsel` may be used for HTTP and HTML extraction.
- **PLT-003**: RSS parsing should use Python standard-library XML parsing unless adding `feedparser` is explicitly accepted as a dependency change.

### Compliance Dependencies

- **COM-001**: Source collection shall respect public-source boundaries and shall avoid private or authenticated communities by default.
- **COM-002**: Documentation shall state that these sources are research inputs, not financial advice, consistent with the project disclaimer.

## 9. Examples & Edge Cases

### 9.1 Explicit Vietnam Symbol

```text
Input ticker: GVR.HM
Provider symbol: GVR
Expected behavior: Use Vietnam sentiment stack. Do not call StockTwits. Do not call US Reddit.
```

### 9.2 Non-Vietnam Symbol With Dot

```text
Input ticker: BRK.B
Expected behavior: Use existing non-Vietnam StockTwits and Reddit path. Do not treat as Vietnam.
```

### 9.3 Ambiguous Plain Local Symbol

```text
Input ticker: GVR
Default expected behavior: Existing non-explicit routing unless a later config-driven Vietnam sentiment rule is added.
Rationale: Plain symbols can be ambiguous across markets.
```

### 9.4 Source Unavailable

```text
Source: VietstockFinance
HTTP result: 403
Expected prompt block: VietstockFinance: <unavailable: HTTP 403>
Expected graph behavior: Continue with other Vietnam sources.
```

### 9.5 No Matching RSS Items

```text
Source: CafeF RSS
RSS item count: 30
Items matching provider symbol: 0
Expected prompt block: CafeF RSS: <no matching items found for GVR in the selected window>
```

## 10. Validation Criteria

- The new specification-compliant implementation shall pass all existing tests.
- New unit tests shall verify no StockTwits or Reddit calls occur for explicit Vietnam symbols.
- New unit tests shall verify existing StockTwits and Reddit calls still occur for non-Vietnam symbols.
- New unit tests shall verify Vietnam provider-symbol normalization for colon-qualified and suffix-qualified inputs.
- New unit tests shall verify DNSE and CafeF parser behavior with fixture payloads.
- New unit tests shall verify unavailable-source placeholders for HTTP and parse failures.
- Static review shall confirm no private or authenticated social sources were added as defaults.
- Documentation review shall confirm Vietnam sentiment limitations are described without implying that the output is financial advice.

## 11. Related Specifications / Further Reading

- [spec-data-vietnam-vnstock-support.md](spec-data-vietnam-vnstock-support.md)
- [spec-design-vnstock-sponsor-module-mapping.md](spec-design-vnstock-sponsor-module-mapping.md)
- `tradingagents/agents/analysts/sentiment_analyst.py`
- `tradingagents/dataflows/vnstock.py`
- `tradingagents/default_config.py`
