"""Vietnam-local sentiment and news source helpers.

The public helper in this module returns prompt-ready text for explicit
Vietnam symbols. It intentionally mirrors the existing sentiment fetchers:
short synchronous HTTP requests, no mandatory extra dependencies, and no
network or parse exceptions escaping to graph execution.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Callable, Iterable
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

import requests
from parsel import Selector

from tradingagents.default_config import normalize_vietnam_provider_symbol

logger = logging.getLogger(__name__)

_UA = "tradingagents/0.2 (+https://github.com/TauricResearch/TradingAgents)"
_HEADERS = {
    "User-Agent": _UA,
    "Accept": "text/html,application/rss+xml,application/xml;q=0.9,*/*;q=0.8",
}

_DNSE_URL = "https://www.dnse.com.vn/senses/co-phieu-{symbol}/tin-tuc"
_VIETSTOCK_URL = "https://finance.vietstock.vn/{symbol}/latest-news.htm"
_F319_RSS_URL = "https://f319.com/forums/thi-truong-chung-khoan.3/index.rss"

_CAFEF_FEEDS = (
    ("CafeF stock market RSS", "https://cafef.vn/thi-truong-chung-khoan.rss"),
    ("CafeF company RSS", "https://cafef.vn/doanh-nghiep.rss"),
    ("CafeF smart money RSS", "https://cafef.vn/smart-money.rss"),
    ("CafeF macro RSS", "https://cafef.vn/vi-mo-dau-tu.rss"),
)

_SKIP_LINK_PREFIXES = ("#", "javascript:", "mailto:", "tel:")
_GUARDED_PAGE_MARKERS = (
    "access denied",
    "captcha",
    "cloudflare",
    "forbidden",
    "just a moment",
)


@dataclass(frozen=True)
class _SourceItem:
    source: str
    title: str
    url: str = ""
    date: str = ""
    excerpt: str = ""
    match_reason: str = ""


def fetch_vietnam_sentiment_sources(
    ticker: str,
    start_date: str,
    end_date: str,
    *,
    include_forums: bool = False,
    limit_per_source: int = 8,
    timeout: float = 10.0,
    issuer_news_block: str | None = None,
) -> str:
    """Return prompt-ready Vietnam news and sentiment source blocks.

    ``ticker`` is preserved in user-facing labels. The provider-local symbol
    is used only for Vietnam source URLs and item matching. ``issuer_news_block``
    lets the sentiment analyst pass the already routed company-news result so
    this helper can include it without making a duplicate vendor call.
    """
    provider_symbol = normalize_vietnam_provider_symbol(ticker)
    source_limit = max(1, int(limit_per_source))

    local_blocks = [
        _safe_block(
            "DNSE Senses",
            lambda: _fetch_dnse_block(provider_symbol, source_limit, timeout),
        ),
        _safe_block(
            "CafeF RSS",
            lambda: _fetch_cafef_block(
                provider_symbol,
                start_date,
                end_date,
                source_limit,
                timeout,
            ),
        ),
        _safe_block(
            "VietstockFinance",
            lambda: _fetch_vietstock_block(provider_symbol, source_limit, timeout),
        ),
    ]

    if include_forums:
        forum_block = _safe_block(
            "F319 public RSS",
            lambda: _fetch_f319_block(
                provider_symbol,
                start_date,
                end_date,
                source_limit,
                timeout,
            ),
        )
    else:
        forum_block = (
            "Source: F319 public RSS\n"
            "Scope: forum-style investor discussion\n"
            "<disabled by default; enable include_forums=True to fetch this noisy public forum source>"
        )

    issuer_block = _format_issuer_block(issuer_news_block)
    return "\n\n".join(
        [
            (
                f"Vietnam sentiment and news sources for {ticker} "
                f"(provider symbol: {provider_symbol})\n"
                f"Window: {start_date} to {end_date}"
            ),
            "## Issuer and company news\n" + issuer_block,
            "## Local financial news\n" + "\n\n".join(local_blocks),
            "## Forum-style investor discussion\n" + forum_block,
        ]
    )


def _request_text(url: str, timeout: float) -> tuple[str | None, str | None]:
    try:
        response = requests.get(url, headers=_HEADERS, timeout=timeout)
    except requests.Timeout:
        return None, "<unavailable: timeout>"
    except requests.RequestException as exc:
        logger.info("Vietnam sentiment source fetch failed for %s: %s", url, exc)
        return None, f"<unavailable: {type(exc).__name__}>"

    if response.status_code >= 400:
        return None, f"<unavailable: HTTP {response.status_code}>"

    text = response.text or ""
    if not text.strip():
        return None, "<unavailable: empty response>"
    return text, None


def _safe_block(source_name: str, build_block: Callable[[], str]) -> str:
    try:
        return build_block()
    except Exception as exc:  # pragma: no cover - defensive guard for graph runs
        logger.info("Vietnam sentiment source %s failed: %s", source_name, exc)
        return f"Source: {source_name}\n<unavailable: {type(exc).__name__}>"


def _format_issuer_block(issuer_news_block: str | None) -> str:
    if issuer_news_block is None:
        return (
            "Source: configured company-news vendor\n"
            "<issuer-scoped company news is collected separately by the sentiment analyst prompt>"
        )
    if not str(issuer_news_block).strip():
        return "Source: configured company-news vendor\n<no issuer-scoped company news returned>"
    return "Source: configured company-news vendor\n" + str(issuer_news_block).strip()


def _fetch_dnse_block(provider_symbol: str, limit: int, timeout: float) -> str:
    url = _DNSE_URL.format(symbol=provider_symbol.lower())
    text, unavailable = _request_text(url, timeout)
    if unavailable:
        return _format_unavailable("DNSE Senses", "ticker page news", provider_symbol, unavailable)
    items = _parse_ticker_page_items(
        text or "",
        source="DNSE Senses",
        base_url=url,
        provider_symbol=provider_symbol,
        match_reason=f"ticker page for {provider_symbol}",
        limit=limit,
    )
    return _format_source_items(
        "DNSE Senses",
        "ticker page news",
        provider_symbol,
        items,
        no_data=f"<no ticker page news items found for {provider_symbol}>",
    )


def _fetch_cafef_block(
    provider_symbol: str,
    start_date: str,
    end_date: str,
    limit: int,
    timeout: float,
) -> str:
    items: list[_SourceItem] = []
    source_notes: list[str] = []

    for feed_name, url in _CAFEF_FEEDS:
        text, unavailable = _request_text(url, timeout)
        if unavailable:
            source_notes.append(f"{feed_name}: {unavailable}")
            continue

        try:
            parsed_items = _parse_rss_items(
                text or "",
                source=feed_name,
                provider_symbol=provider_symbol,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                require_symbol_match=True,
            )
        except ET.ParseError:
            source_notes.append(f"{feed_name}: <unavailable: invalid RSS XML>")
            continue
        items.extend(parsed_items)

    items = _dedupe_items(items)[:limit]
    block = _format_source_items(
        "CafeF RSS",
        "local financial news",
        provider_symbol,
        items,
        no_data=(
            f"<no matching items found for {provider_symbol} in CafeF RSS "
            f"between {start_date} and {end_date}>"
        ),
    )
    if source_notes:
        block += "\nSource notes:\n" + "\n".join(f"- {note}" for note in source_notes)
    return block


def _fetch_vietstock_block(provider_symbol: str, limit: int, timeout: float) -> str:
    url = _VIETSTOCK_URL.format(symbol=provider_symbol.upper())
    text, unavailable = _request_text(url, timeout)
    if unavailable:
        return _format_unavailable("VietstockFinance", "ticker page news", provider_symbol, unavailable)

    lowered = (text or "").lower()
    if any(marker in lowered for marker in _GUARDED_PAGE_MARKERS):
        return _format_unavailable(
            "VietstockFinance",
            "ticker page news",
            provider_symbol,
            "<unavailable: guarded page>",
        )

    items = _parse_ticker_page_items(
        text or "",
        source="VietstockFinance",
        base_url=url,
        provider_symbol=provider_symbol,
        match_reason=f"ticker page for {provider_symbol}",
        limit=limit,
    )
    return _format_source_items(
        "VietstockFinance",
        "ticker page news",
        provider_symbol,
        items,
        no_data=f"<no ticker page news items found for {provider_symbol}>",
    )


def _fetch_f319_block(
    provider_symbol: str,
    start_date: str,
    end_date: str,
    limit: int,
    timeout: float,
) -> str:
    text, unavailable = _request_text(_F319_RSS_URL, timeout)
    if unavailable:
        return _format_unavailable("F319 public RSS", "forum-style investor discussion", provider_symbol, unavailable)

    try:
        items = _parse_rss_items(
            text or "",
            source="F319 public RSS",
            provider_symbol=provider_symbol,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            require_symbol_match=True,
        )
    except ET.ParseError:
        return _format_unavailable(
            "F319 public RSS",
            "forum-style investor discussion",
            provider_symbol,
            "<unavailable: invalid RSS XML>",
        )

    return _format_source_items(
        "F319 public RSS",
        "forum-style investor discussion",
        provider_symbol,
        items,
        no_data=f"<no matching forum items found for {provider_symbol} between {start_date} and {end_date}>",
    )


def _parse_ticker_page_items(
    text: str,
    *,
    source: str,
    base_url: str,
    provider_symbol: str,
    match_reason: str,
    limit: int,
) -> list[_SourceItem]:
    selector = Selector(text=text)
    items: list[_SourceItem] = []
    for anchor in selector.css("a"):
        href = (anchor.attrib.get("href") or "").strip()
        if not href or href.lower().startswith(_SKIP_LINK_PREFIXES):
            continue

        title = _clean_text(" ".join(anchor.css("::text").getall()))
        if not title or len(title) < 8:
            continue

        url = urljoin(base_url, href)
        items.append(
            _SourceItem(
                source=source,
                title=_truncate(title, 220),
                url=url,
                match_reason=match_reason,
            )
        )
        if len(items) >= limit:
            break

    return _dedupe_items(items)


def _parse_rss_items(
    text: str,
    *,
    source: str,
    provider_symbol: str,
    start_date: str,
    end_date: str,
    limit: int,
    require_symbol_match: bool,
) -> list[_SourceItem]:
    root = ET.fromstring(text)
    items: list[_SourceItem] = []
    for element in _iter_elements_named(root, "item"):
        title = _clean_text(_child_text(element, "title"))
        description = _clean_text(_child_text(element, "description"))
        url = _clean_text(_child_text(element, "link"))
        published_raw = _clean_text(_child_text(element, "pubDate"))
        published_date = _format_feed_date(published_raw)

        searchable = f"{title} {description}"
        if require_symbol_match and not _matches_symbol(searchable, provider_symbol):
            continue
        if not _date_in_window(published_raw, start_date, end_date):
            continue
        if not title:
            continue

        items.append(
            _SourceItem(
                source=source,
                title=_truncate(title, 220),
                url=url,
                date=published_date,
                excerpt=_truncate(description, 260),
                match_reason=f"matched provider symbol {provider_symbol}",
            )
        )
        if len(items) >= limit:
            break

    return _dedupe_items(items)


def _iter_elements_named(root: ET.Element, name: str) -> Iterable[ET.Element]:
    for element in root.iter():
        if _tag_name(element.tag) == name:
            yield element


def _child_text(element: ET.Element, child_name: str) -> str:
    for child in element:
        if _tag_name(child.tag) == child_name:
            return "".join(child.itertext()).strip()
    return ""


def _tag_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _format_source_items(
    source_name: str,
    scope: str,
    provider_symbol: str,
    items: list[_SourceItem],
    *,
    no_data: str,
) -> str:
    lines = [
        f"Source: {source_name}",
        f"Scope: {scope}",
        f"Target provider symbol: {provider_symbol}",
    ]
    if not items:
        lines.append(no_data)
        return "\n".join(lines)

    for item in items:
        date_prefix = f"[{item.date}] " if item.date else ""
        lines.append(f"- {date_prefix}{item.title}")
        if item.url:
            lines.append(f"  URL: {item.url}")
        if item.excerpt:
            lines.append(f"  Excerpt: {item.excerpt}")
        if item.match_reason:
            lines.append(f"  Match: {item.match_reason}")
    return "\n".join(lines)


def _format_unavailable(source_name: str, scope: str, provider_symbol: str, reason: str) -> str:
    return "\n".join(
        [
            f"Source: {source_name}",
            f"Scope: {scope}",
            f"Target provider symbol: {provider_symbol}",
            reason,
        ]
    )


def _dedupe_items(items: Iterable[_SourceItem]) -> list[_SourceItem]:
    deduped = []
    seen = set()
    for item in items:
        key = (item.source, item.title.lower(), item.url)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _matches_symbol(text: str, provider_symbol: str) -> bool:
    pattern = rf"(?<![A-Z0-9]){re.escape(provider_symbol.upper())}(?![A-Z0-9])"
    return re.search(pattern, text.upper()) is not None


def _date_in_window(published_raw: str, start_date: str, end_date: str) -> bool:
    published = _parse_feed_datetime(published_raw)
    if published is None:
        return True

    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    return start <= published.date() <= end


def _format_feed_date(published_raw: str) -> str:
    published = _parse_feed_datetime(published_raw)
    if published is None:
        return ""
    return published.strftime("%Y-%m-%d")


def _parse_feed_datetime(published_raw: str) -> datetime | None:
    if not published_raw:
        return None

    for parser in (_parse_rfc2822_datetime, _parse_iso_datetime):
        parsed = parser(published_raw)
        if parsed is not None:
            return parsed.replace(tzinfo=None)
    return None


def _parse_rfc2822_datetime(value: str) -> datetime | None:
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None


def _parse_iso_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _clean_text(value: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", unescape(value or ""))
    return re.sub(r"\s+", " ", cleaned).strip()


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "..."