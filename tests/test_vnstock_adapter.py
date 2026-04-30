import types

import pandas as pd
import pytest

from tradingagents.dataflows import vnstock


class FakeQuote:
    seen_symbols = []

    def __init__(self, symbol, source=None):
        self.symbol = symbol
        self.source = source
        FakeQuote.seen_symbols.append(symbol)

    def history(self, start, end, interval="1D"):
        return pd.DataFrame({
            "time": ["2025-12-31", "2026-01-02", "2026-01-05", "2026-02-01"],
            "open": [99000, 100000, 101000, 110000],
            "high": [99500, 101000, 102000, 111000],
            "low": [98000, 99500, 100500, 109000],
            "close": [99200, 100500, 101500, 110500],
            "volume": [900, 1200, 1500, 2000],
        })


def _fake_module(**attrs):
    return types.SimpleNamespace(**attrs)


@pytest.mark.unit
def test_normalize_vietnam_symbol_variants():
    assert vnstock._normalize_vietnam_symbol(" fpt ") == "FPT"
    assert vnstock._normalize_vietnam_symbol("HOSE:FPT") == "FPT"
    assert vnstock._normalize_vietnam_symbol("HNX:SHS") == "SHS"
    assert vnstock._normalize_vietnam_symbol("UPCOM:ABC") == "ABC"
    assert vnstock._normalize_vietnam_symbol("FPT.HM") == "FPT"
    assert vnstock._normalize_vietnam_symbol("SHS.HN") == "SHS"
    assert vnstock._normalize_vietnam_symbol("7203.T") == "7203.T"
    assert vnstock._normalize_vietnam_symbol("BRK.B") == "BRK.B"


@pytest.mark.unit
def test_get_stock_formats_canonical_ohlcv(monkeypatch):
    FakeQuote.seen_symbols = []
    monkeypatch.setattr(vnstock, "_load_vnstock", lambda: _fake_module(Quote=FakeQuote))

    result = vnstock.get_stock("HOSE:FPT", "2026-01-01", "2026-01-31")

    assert FakeQuote.seen_symbols == ["FPT"]
    assert "# Stock data for FPT from 2026-01-01 to 2026-01-31" in result
    assert "# Vendor: vnstock" in result
    assert "# Currency: VND" in result
    assert "Date,Open,High,Low,Close,Volume" in result
    assert "2026-01-02,100000,101000,99500,100500,1200" in result
    assert "2025-12-31" not in result
    assert "2026-02-01" not in result


@pytest.mark.unit
def test_get_indicator_uses_vnstock_ohlcv(monkeypatch):
    dates = pd.date_range("2025-11-01", "2026-01-10", freq="D")
    data = pd.DataFrame({
        "time": dates,
        "open": range(100, 100 + len(dates)),
        "high": range(101, 101 + len(dates)),
        "low": range(99, 99 + len(dates)),
        "close": range(100, 100 + len(dates)),
        "volume": [1000] * len(dates),
    })

    class IndicatorQuote:
        def __init__(self, symbol, source=None):
            self.symbol = symbol

        def history(self, start, end, interval="1D"):
            return data

    monkeypatch.setattr(vnstock, "_load_vnstock", lambda: _fake_module(Quote=IndicatorQuote))

    result = vnstock.get_indicator("FPT", "rsi", "2026-01-10", 2)

    assert "## rsi values from 2026-01-08 to 2026-01-10" in result
    assert "2026-01-10:" in result
    assert "RSI: Measures momentum" in result


@pytest.mark.unit
def test_get_indicator_rejects_unsupported_indicator():
    with pytest.raises(ValueError, match="Indicator nope is not supported"):
        vnstock.get_indicator("FPT", "nope", "2026-01-10", 5)


@pytest.mark.unit
def test_financial_statement_filters_future_periods(monkeypatch):
    class FakeFinance:
        def __init__(self, symbol, source=None):
            self.symbol = symbol

        def balance_sheet(self, period="quarter", lang="en", dropna=True):
            return pd.DataFrame({
                "period": ["2025-Q4", "2026-Q1", "2026-Q2"],
                "total_assets": [100, 120, 140],
            })

    monkeypatch.setattr(vnstock, "_load_vnstock", lambda: _fake_module(Finance=FakeFinance))

    result = vnstock.get_balance_sheet("FPT", curr_date="2026-03-31")

    assert "2025-Q4" in result
    assert "2026-Q1" in result
    assert "2026-Q2" not in result


@pytest.mark.unit
def test_news_unavailable_returns_clear_message(monkeypatch):
    class FakeCompany:
        def __init__(self, symbol, source=None):
            self.symbol = symbol

    monkeypatch.setattr(vnstock, "_load_vnstock", lambda: _fake_module(Company=FakeCompany))

    result = vnstock.get_news("FPT", "2026-01-01", "2026-01-31")

    assert result == "No vnstock news data available for FPT between 2026-01-01 and 2026-01-31."


@pytest.mark.unit
def test_insider_transactions_unavailable_returns_clear_message():
    result = vnstock.get_insider_transactions("HOSE:FPT")

    assert result == "vnstock does not provide insider transaction data through the configured adapter for FPT."
