import pytest

from tradingagents.graph.trading_graph import TradingAgentsGraph


@pytest.mark.unit
@pytest.mark.parametrize(
    ("provider", "config_key", "config_value", "expected_key"),
    [
        ("openai", "openai_reasoning_effort", "high", "reasoning_effort"),
        ("openrouter", "openrouter_reasoning_effort", "high", "reasoning_effort"),
        ("google", "google_thinking_level", "high", "thinking_level"),
        ("anthropic", "anthropic_effort", "medium", "effort"),
    ],
)
def test_provider_kwargs_include_timeout_and_provider_specific_setting(
    provider,
    config_key,
    config_value,
    expected_key,
):
    graph = TradingAgentsGraph.__new__(TradingAgentsGraph)
    graph.config = {
        "llm_provider": provider,
        "llm_timeout": 30,
        config_key: config_value,
    }

    kwargs = TradingAgentsGraph._get_provider_kwargs(graph)

    assert kwargs["timeout"] == 30
    assert kwargs[expected_key] == config_value


@pytest.mark.unit
def test_provider_kwargs_skip_timeout_when_not_configured():
    graph = TradingAgentsGraph.__new__(TradingAgentsGraph)
    graph.config = {
        "llm_provider": "openai",
        "openai_reasoning_effort": "low",
    }

    kwargs = TradingAgentsGraph._get_provider_kwargs(graph)

    assert "timeout" not in kwargs
    assert kwargs["reasoning_effort"] == "low"


@pytest.mark.unit
def test_provider_kwargs_skip_openrouter_reasoning_when_not_configured():
    graph = TradingAgentsGraph.__new__(TradingAgentsGraph)
    graph.config = {
        "llm_provider": "openrouter",
    }

    kwargs = TradingAgentsGraph._get_provider_kwargs(graph)

    assert kwargs == {}