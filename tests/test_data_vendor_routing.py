import pytest
from types import SimpleNamespace

from tradingagents.dataflows import interface
from tradingagents.dataflows.config import get_config, set_config
from tradingagents.dataflows.errors import DataVendorUnavailableError
from tradingagents.default_config import DEFAULT_CONFIG, resolve_config
from tradingagents.graph.trading_graph import TradingAgentsGraph


@pytest.fixture(autouse=True)
def reset_config():
    set_config(DEFAULT_CONFIG.copy())
    yield
    set_config(DEFAULT_CONFIG.copy())


@pytest.mark.unit
def test_vnstock_registered_for_required_methods():
    assert "vnstock" in interface.VENDOR_LIST
    for method in [
        "get_stock_data",
        "get_indicators",
        "get_fundamentals",
        "get_balance_sheet",
        "get_cashflow",
        "get_income_statement",
        "get_news",
        "get_global_news",
    ]:
        assert "vnstock" in interface.VENDOR_METHODS[method]


@pytest.mark.unit
def test_route_falls_back_when_vnstock_unavailable(monkeypatch):
    calls = []

    def unavailable(*args, **kwargs):
        calls.append("vnstock")
        raise DataVendorUnavailableError("vnstock missing")

    def fallback(*args, **kwargs):
        calls.append("yfinance")
        return "fallback data"

    monkeypatch.setitem(
        interface.VENDOR_METHODS,
        "get_stock_data",
        {"vnstock": unavailable, "yfinance": fallback},
    )
    set_config({"data_vendors": {"core_stock_apis": "vnstock,yfinance"}})

    result = interface.route_to_vendor("get_stock_data", "FPT", "2026-01-01", "2026-01-31")

    assert result == "fallback data"
    assert calls == ["vnstock", "yfinance"]


@pytest.mark.unit
def test_route_explicit_vietnam_symbol_prefers_vnstock_over_default_yfinance(monkeypatch):
    calls = []

    def yfinance(*args, **kwargs):
        calls.append("yfinance")
        return "yfinance data"

    def vnstock(*args, **kwargs):
        calls.append("vnstock")
        return "vnstock data"

    monkeypatch.setitem(
        interface.VENDOR_METHODS,
        "get_stock_data",
        {"yfinance": yfinance, "vnstock": vnstock},
    )
    set_config({"data_vendors": {"core_stock_apis": "yfinance"}})

    result = interface.route_to_vendor("get_stock_data", "HOSE:VIC", "2026-01-01", "2026-01-31")

    assert result == "vnstock data"
    assert calls == ["vnstock"]


@pytest.mark.unit
def test_route_plain_symbol_keeps_configured_yfinance(monkeypatch):
    calls = []

    def yfinance(*args, **kwargs):
        calls.append("yfinance")
        return "yfinance data"

    def vnstock(*args, **kwargs):
        calls.append("vnstock")
        return "vnstock data"

    monkeypatch.setitem(
        interface.VENDOR_METHODS,
        "get_stock_data",
        {"yfinance": yfinance, "vnstock": vnstock},
    )
    set_config({"data_vendors": {"core_stock_apis": "yfinance"}})

    result = interface.route_to_vendor("get_stock_data", "VIC", "2026-01-01", "2026-01-31")

    assert result == "yfinance data"
    assert calls == ["yfinance"]


@pytest.mark.unit
def test_graph_applies_vietnam_profile_at_propagate_time():
    graph = SimpleNamespace(
        config=resolve_config({"data_vendors": {"core_stock_apis": "yfinance"}}),
        reflector=SimpleNamespace(benchmark_label="SPY"),
    )

    TradingAgentsGraph._apply_symbol_market_profile(graph, "HOSE:VIC")

    assert graph.config["market_profile"] == "vietnam"
    assert graph.config["benchmark_symbol"] == "VNINDEX"
    assert graph.config["currency"] == "VND"
    assert graph.config["data_vendors"]["core_stock_apis"] == "vnstock,yfinance"
    assert graph.reflector.benchmark_label == "VNINDEX"
    assert get_config()["data_vendors"]["core_stock_apis"] == "vnstock,yfinance"


@pytest.mark.unit
def test_vietnam_market_profile_sets_benchmark_and_currency_from_default_copy():
    config = DEFAULT_CONFIG.copy()
    config["market_profile"] = "vietnam"

    resolved = resolve_config(config)

    assert resolved["benchmark_symbol"] == "VNINDEX"
    assert resolved["currency"] == "VND"


@pytest.mark.unit
def test_default_market_profile_preserves_existing_benchmark_and_currency():
    resolved = resolve_config(DEFAULT_CONFIG.copy())

    assert resolved["benchmark_symbol"] == "SPY"
    assert resolved["currency"] == "USD"
