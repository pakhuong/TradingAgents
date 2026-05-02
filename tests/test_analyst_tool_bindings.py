from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
import pytest

from tradingagents.agents.analysts.fundamentals_analyst import create_fundamentals_analyst
from tradingagents.graph.trading_graph import TradingAgentsGraph


class _CapturingLLM:
    def __init__(self, captured):
        self.captured = captured

    def bind_tools(self, tools):
        self.captured["tools"] = tools

        def _invoke(prompt_value):
            self.captured["prompt"] = prompt_value
            return AIMessage(content="fundamentals report")

        return RunnableLambda(_invoke)


@pytest.mark.unit
def test_fundamentals_analyst_binds_insider_transactions_tool():
    captured = {}
    analyst = create_fundamentals_analyst(_CapturingLLM(captured))

    result = analyst(
        {
            "trade_date": "2026-01-31",
            "company_of_interest": "HOSE:FPT",
            "messages": [],
        }
    )

    assert result["fundamentals_report"] == "fundamentals report"
    assert [tool.name for tool in captured["tools"]] == [
        "get_fundamentals",
        "get_balance_sheet",
        "get_cashflow",
        "get_income_statement",
        "get_insider_transactions",
    ]

    prompt_text = "\n".join(str(message.content) for message in captured["prompt"].messages)
    assert "get_insider_transactions" in prompt_text
    assert "insider trading activity" in prompt_text


@pytest.mark.unit
def test_fundamentals_tool_node_exposes_insider_transactions_tool():
    graph = TradingAgentsGraph.__new__(TradingAgentsGraph)

    tool_nodes = TradingAgentsGraph._create_tool_nodes(graph)

    assert "get_insider_transactions" in tool_nodes["fundamentals"].tools_by_name