import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from langchain_openai import ChatOpenAI

from tradingagents.llm_clients.openai_client import NormalizedChatOpenAI, OpenAIClient


def _make_llm(base_url: str = "https://openrouter.ai/api/v1") -> NormalizedChatOpenAI:
    return NormalizedChatOpenAI(
        model="deepseek/deepseek-v4-flash",
        api_key="test-key",
        base_url=base_url,
    )


@pytest.mark.unit
def test_normalized_chat_openai_retries_once_on_json_decode_error():
    llm = _make_llm()
    response = SimpleNamespace(content="ok")

    with patch.object(
        ChatOpenAI,
        "invoke",
        side_effect=[json.JSONDecodeError("Expecting value", " \n", 2), response],
    ) as invoke_mock:
        result = llm.invoke("hello")

    assert result is response
    assert invoke_mock.call_count == 2


@pytest.mark.unit
def test_normalized_chat_openai_raises_runtime_error_after_repeated_malformed_responses():
    llm = _make_llm()
    first_error = json.JSONDecodeError("Expecting value", " \n", 2)
    second_error = json.JSONDecodeError("Expecting value", " \n", 2)

    with patch.object(
        ChatOpenAI,
        "invoke",
        side_effect=[first_error, second_error],
    ):
        with pytest.raises(RuntimeError, match="malformed JSON") as exc_info:
            llm.invoke("hello")

    assert "openrouter.ai/api/v1" in str(exc_info.value)
    assert "deepseek/deepseek-v4-flash" in str(exc_info.value)


@pytest.mark.unit
def test_openrouter_client_translates_reasoning_effort_to_extra_body():
    client = OpenAIClient(
        model="openai/gpt-5",
        provider="openrouter",
        reasoning_effort="high",
    )

    with patch("tradingagents.llm_clients.openai_client.NormalizedChatOpenAI") as llm_cls:
        client.get_llm()

    kwargs = llm_cls.call_args.kwargs
    assert kwargs["extra_body"] == {"reasoning": {"effort": "high"}}
    assert "reasoning_effort" not in kwargs
    assert "use_responses_api" not in kwargs


@pytest.mark.unit
def test_openrouter_client_merges_existing_extra_body():
    client = OpenAIClient(
        model="openai/gpt-5",
        provider="openrouter",
        reasoning_effort="high",
        extra_body={"provider": {"allow_fallbacks": True}},
    )

    with patch("tradingagents.llm_clients.openai_client.NormalizedChatOpenAI") as llm_cls:
        client.get_llm()

    kwargs = llm_cls.call_args.kwargs
    assert kwargs["extra_body"] == {
        "provider": {"allow_fallbacks": True},
        "reasoning": {"effort": "high"},
    }


@pytest.mark.unit
def test_openrouter_client_merges_existing_reasoning_mapping():
    client = OpenAIClient(
        model="openai/gpt-5",
        provider="openrouter",
        reasoning_effort="high",
        extra_body={"reasoning": {"exclude": True}},
    )

    with patch("tradingagents.llm_clients.openai_client.NormalizedChatOpenAI") as llm_cls:
        client.get_llm()

    kwargs = llm_cls.call_args.kwargs
    assert kwargs["extra_body"] == {
        "reasoning": {"exclude": True, "effort": "high"},
    }


@pytest.mark.unit
def test_openrouter_client_rejects_non_mapping_reasoning_block():
    client = OpenAIClient(
        model="openai/gpt-5",
        provider="openrouter",
        reasoning_effort="high",
        extra_body={"reasoning": "bad-shape"},
    )

    with pytest.raises(ValueError, match="extra_body.reasoning"):
        client.get_llm()


@pytest.mark.unit
def test_native_openai_client_keeps_reasoning_effort_and_responses_api():
    client = OpenAIClient(
        model="gpt-5.4",
        provider="openai",
        reasoning_effort="low",
    )

    with patch("tradingagents.llm_clients.openai_client.NormalizedChatOpenAI") as llm_cls:
        client.get_llm()

    kwargs = llm_cls.call_args.kwargs
    assert kwargs["reasoning_effort"] == "low"
    assert kwargs["use_responses_api"] is True
    assert "extra_body" not in kwargs