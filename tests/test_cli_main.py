from unittest.mock import MagicMock

import cli.main as cli_main
from cli.models import AnalystType


class DummyLive:
    def __init__(self, *_args, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class DummyStatsHandler:
    pass


class DummyGraph:
    last_instance = None

    def __init__(self, selected_analysts, config=None, debug=False, callbacks=None):
        DummyGraph.last_instance = self
        self.selected_analysts = selected_analysts
        self.config = config or {}
        self.debug = debug
        self.callbacks = callbacks or []
        self.graph = MagicMock()
        self.graph.stream.side_effect = AssertionError(
            "CLI should delegate to TradingAgentsGraph.propagate()."
        )
        self.propagate_calls = []

    def propagate(
        self,
        ticker,
        trade_date,
        asset_type="stock",
        runtime_callbacks=None,
        chunk_handler=None,
    ):
        self.propagate_calls.append(
            {
                "ticker": ticker,
                "trade_date": trade_date,
                "asset_type": asset_type,
                "runtime_callbacks": runtime_callbacks,
                "chunk_handler": chunk_handler,
            }
        )
        if chunk_handler is not None:
            chunk_handler({"messages": []})

        final_state = {
            "market_report": "Market report.",
            "investment_plan": "Investment plan.",
            "trader_investment_plan": "Trader plan.",
            "final_trade_decision": "Rating: Buy\nBuy NVDA.",
        }
        return final_state, "Buy"


def test_run_analysis_delegates_to_propagate(monkeypatch, tmp_path):
    monkeypatch.setattr(cli_main, "message_buffer", cli_main.MessageBuffer())
    monkeypatch.setattr(cli_main, "TradingAgentsGraph", DummyGraph)
    monkeypatch.setattr(cli_main, "StatsCallbackHandler", DummyStatsHandler)
    monkeypatch.setattr(cli_main, "Live", DummyLive)
    monkeypatch.setattr(cli_main, "create_layout", lambda: {})
    monkeypatch.setattr(cli_main, "update_display", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli_main.console, "print", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli_main.typer, "prompt", lambda *_args, **_kwargs: "N")
    monkeypatch.setitem(cli_main.DEFAULT_CONFIG, "results_dir", str(tmp_path / "results"))

    monkeypatch.setattr(
        cli_main,
        "get_user_selections",
        lambda: {
            "ticker": "NVDA",
            "asset_type": "stock",
            "analysis_date": "2026-01-10",
            "analysts": [AnalystType.MARKET],
            "research_depth": 1,
            "llm_provider": "openai",
            "backend_url": None,
            "shallow_thinker": "gpt-5.4-mini",
            "deep_thinker": "gpt-5.4",
            "google_thinking_level": None,
            "openai_reasoning_effort": None,
            "openrouter_reasoning_effort": None,
            "anthropic_effort": None,
            "output_language": "English",
        },
    )

    cli_main.run_analysis(checkpoint=False)

    graph = DummyGraph.last_instance
    assert graph is not None
    assert len(graph.propagate_calls) == 1
    call = graph.propagate_calls[0]
    assert call["ticker"] == "NVDA"
    assert call["trade_date"] == "2026-01-10"
    assert call["asset_type"] == "stock"
    assert call["runtime_callbacks"]
    assert callable(call["chunk_handler"])
    graph.graph.stream.assert_not_called()


def test_run_analysis_encodes_exchange_qualified_ticker_in_results_path(monkeypatch, tmp_path):
    monkeypatch.setattr(cli_main, "message_buffer", cli_main.MessageBuffer())
    monkeypatch.setattr(cli_main, "TradingAgentsGraph", DummyGraph)
    monkeypatch.setattr(cli_main, "StatsCallbackHandler", DummyStatsHandler)
    monkeypatch.setattr(cli_main, "Live", DummyLive)
    monkeypatch.setattr(cli_main, "create_layout", lambda: {})
    monkeypatch.setattr(cli_main, "update_display", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli_main.console, "print", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli_main.typer, "prompt", lambda *_args, **_kwargs: "N")
    monkeypatch.setitem(cli_main.DEFAULT_CONFIG, "results_dir", str(tmp_path / "results"))

    monkeypatch.setattr(
        cli_main,
        "get_user_selections",
        lambda: {
            "ticker": "HOSE:GVR",
            "asset_type": "stock",
            "analysis_date": "2026-01-10",
            "analysts": [AnalystType.MARKET],
            "research_depth": 1,
            "llm_provider": "openai",
            "backend_url": None,
            "shallow_thinker": "gpt-5.4-mini",
            "deep_thinker": "gpt-5.4",
            "google_thinking_level": None,
            "openai_reasoning_effort": None,
            "openrouter_reasoning_effort": None,
            "anthropic_effort": None,
            "output_language": "English",
        },
    )

    cli_main.run_analysis(checkpoint=False)

    encoded_run_dir = tmp_path / "results" / "HOSE%3AGVR" / "2026-01-10"
    assert encoded_run_dir.is_dir()
    assert not (tmp_path / "results" / "HOSE:GVR").exists()
    assert (encoded_run_dir / "message_tool.log").exists()

    graph = DummyGraph.last_instance
    assert graph is not None
    assert graph.propagate_calls[0]["ticker"] == "HOSE:GVR"
