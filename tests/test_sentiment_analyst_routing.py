from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from tradingagents.agents.analysts import sentiment_analyst


def _capturing_llm(captured):
    def invoke(prompt_value):
        captured["prompt"] = prompt_value
        return AIMessage(content="sentiment report")

    return RunnableLambda(invoke)


def _prompt_text(captured):
    return "\n".join(str(message.content) for message in captured["prompt"].messages)


@pytest.mark.unit
@pytest.mark.parametrize("ticker", ["HOSE:GVR", "GVR.HM"])
def test_sentiment_analyst_uses_vietnam_sources_for_explicit_symbol(monkeypatch, ticker):
    calls = {"news": [], "vietnam": []}

    def fake_news(ticker, start_date, end_date):
        calls["news"].append((ticker, start_date, end_date))
        return f"issuer news for {ticker}"

    def fake_vietnam_sources(**kwargs):
        calls["vietnam"].append(kwargs)
        return f"Vietnam block for {ticker} with local market news"

    def fail_us_source(*args, **kwargs):
        raise AssertionError("US social source should not be fetched")

    monkeypatch.setattr(sentiment_analyst, "get_news", SimpleNamespace(func=fake_news))
    monkeypatch.setattr(sentiment_analyst, "fetch_vietnam_sentiment_sources", fake_vietnam_sources)
    monkeypatch.setattr(sentiment_analyst, "fetch_stocktwits_messages", fail_us_source)
    monkeypatch.setattr(sentiment_analyst, "fetch_reddit_posts", fail_us_source)

    captured = {}
    analyst = sentiment_analyst.create_sentiment_analyst(_capturing_llm(captured))

    result = analyst(
        {
            "trade_date": "2026-05-16",
            "company_of_interest": ticker,
            "messages": [],
        }
    )

    assert result["sentiment_report"] == "sentiment report"
    assert calls["news"] == [(ticker, "2026-05-09", "2026-05-16")]
    assert calls["vietnam"][0]["ticker"] == ticker
    assert calls["vietnam"][0]["issuer_news_block"] == f"issuer news for {ticker}"

    prompt_text = _prompt_text(captured)
    assert ticker in prompt_text
    assert "News headlines and company disclosures" in prompt_text
    assert "Vietnam local market news" in prompt_text
    assert "Vietnam investor forum discussion" in prompt_text
    assert "StockTwits messages" not in prompt_text
    assert "Reddit posts" not in prompt_text


@pytest.mark.unit
def test_sentiment_analyst_keeps_us_sources_for_non_vietnam_symbol(monkeypatch):
    calls = {"news": [], "stocktwits": [], "reddit": []}

    def fake_news(ticker, start_date, end_date):
        calls["news"].append((ticker, start_date, end_date))
        return "AAPL news block"

    def fake_stocktwits(ticker, **kwargs):
        calls["stocktwits"].append((ticker, kwargs))
        return "AAPL stocktwits block"

    def fake_reddit(ticker, **kwargs):
        calls["reddit"].append((ticker, kwargs))
        return "AAPL reddit block"

    def fail_vietnam_source(*args, **kwargs):
        raise AssertionError("Vietnam source should not be fetched")

    monkeypatch.setattr(sentiment_analyst, "get_news", SimpleNamespace(func=fake_news))
    monkeypatch.setattr(sentiment_analyst, "fetch_stocktwits_messages", fake_stocktwits)
    monkeypatch.setattr(sentiment_analyst, "fetch_reddit_posts", fake_reddit)
    monkeypatch.setattr(sentiment_analyst, "fetch_vietnam_sentiment_sources", fail_vietnam_source)

    captured = {}
    analyst = sentiment_analyst.create_sentiment_analyst(_capturing_llm(captured))

    result = analyst(
        {
            "trade_date": "2026-05-16",
            "company_of_interest": "AAPL",
            "messages": [],
        }
    )

    assert result["sentiment_report"] == "sentiment report"
    assert calls["news"] == [("AAPL", "2026-05-09", "2026-05-16")]
    assert calls["stocktwits"][0][0] == "AAPL"
    assert calls["stocktwits"][0][1] == {"limit": 30}
    assert calls["reddit"] == [("AAPL", {})]

    prompt_text = _prompt_text(captured)
    assert "StockTwits messages" in prompt_text
    assert "Reddit posts" in prompt_text
    assert "Vietnam local market news" not in prompt_text


@pytest.mark.unit
def test_sentiment_analyst_keeps_dot_ticker_on_us_path(monkeypatch):
    calls = {"stocktwits": 0, "reddit": 0}

    monkeypatch.setattr(
        sentiment_analyst,
        "get_news",
        SimpleNamespace(func=lambda ticker, start_date, end_date: "BRK.B news block"),
    )
    monkeypatch.setattr(
        sentiment_analyst,
        "fetch_stocktwits_messages",
        lambda ticker, **kwargs: calls.__setitem__("stocktwits", calls["stocktwits"] + 1) or "stocktwits",
    )
    monkeypatch.setattr(
        sentiment_analyst,
        "fetch_reddit_posts",
        lambda ticker, **kwargs: calls.__setitem__("reddit", calls["reddit"] + 1) or "reddit",
    )
    monkeypatch.setattr(
        sentiment_analyst,
        "fetch_vietnam_sentiment_sources",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Vietnam source should not be fetched")),
    )

    captured = {}
    analyst = sentiment_analyst.create_sentiment_analyst(_capturing_llm(captured))
    analyst({"trade_date": "2026-05-16", "company_of_interest": "BRK.B", "messages": []})

    assert calls == {"stocktwits": 1, "reddit": 1}