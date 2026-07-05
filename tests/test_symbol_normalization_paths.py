"""Symbol normalization must apply on every yfinance path, not just price fetch.

Regression tests for #983 (instrument identity), #984 (reflection returns), and
the news path: a broker symbol like XAUUSD must resolve to the same Yahoo symbol
(GC=F) that the price path uses, so identity, realized-return, and news lookups
hit the right instrument instead of failing/mismatching.
"""
import tradingagents.agents.utils.agent_utils as au
import tradingagents.dataflows.yfinance_news as ynews
import tradingagents.graph.trading_graph as tg
from tradingagents.graph.trading_graph import TradingAgentsGraph


def test_identity_lookup_normalizes_symbol(monkeypatch):
    seen = {}

    class FakeTicker:
        def __init__(self, symbol):
            seen["symbol"] = symbol

        @property
        def info(self):
            return {"longName": "Gold Futures", "quoteType": "FUTURE"}

    monkeypatch.setattr(au.yf, "Ticker", FakeTicker)
    au.resolve_instrument_identity.cache_clear()

    identity = au.resolve_instrument_identity("XAUUSD")

    assert seen["symbol"] == "GC=F"  # normalized, not the raw broker symbol
    assert identity.get("company_name") == "Gold Futures"


def test_fetch_returns_normalizes_symbol(monkeypatch):
    queried = []

    def fake_route(tool_name, symbol, start_date, end_date):
        queried.append((tool_name, symbol, start_date, end_date))
        return "\n".join(
            [
                "Date,Close",
                "2025-01-02,100.0",
                "2025-01-03,101.0",
                "2025-01-04,102.0",
                "2025-01-05,103.0",
                "2025-01-06,104.0",
                "2025-01-07,105.0",
                "2025-01-08,106.0",
            ]
        )

    monkeypatch.setattr(tg, "route_to_vendor", fake_route)

    # Build a minimal instance to avoid full graph construction while still
    # exercising the real _fetch_close_prices vendor boundary.
    graph = TradingAgentsGraph.__new__(TradingAgentsGraph)
    graph.config = {}
    raw, alpha, days = TradingAgentsGraph._fetch_returns(
        graph, "XAUUSD", "2025-01-02", holding_days=5, benchmark="SPY"
    )

    assert queried[0][0] == "get_stock_data"
    assert queried[0][1] == "GC=F"  # stock symbol normalized (#984)
    assert queried[1][1] == "SPY"   # benchmark left as the canonical symbol
    assert raw is not None and days is not None


def test_news_lookup_normalizes_symbol(monkeypatch):
    seen = {}

    class FakeTicker:
        def __init__(self, symbol):
            seen["symbol"] = symbol

        def get_news(self, count):
            return []

    monkeypatch.setattr(ynews.yf, "Ticker", FakeTicker)
    monkeypatch.setattr(ynews, "yf_retry", lambda fn: fn())

    out = ynews.get_news_yfinance("XAUUSD", "2025-01-01", "2025-01-10")

    assert seen["symbol"] == "GC=F"   # news queried with the canonical symbol
    assert "XAUUSD" in out            # the user's ticker stays in the report
    assert "GC=F" in out              # provenance noted
