import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from langchain_openai import ChatOpenAI

from tradingagents.llm_clients.openai_client import NormalizedChatOpenAI


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