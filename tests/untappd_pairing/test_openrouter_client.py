import logging
from unittest import mock

import pytest

from untappd_pairing import openrouter_client


@pytest.fixture(autouse=True)
def _api_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)


def _response(content=None, reasoning=None):
    message = mock.MagicMock()
    message.content = content
    message.reasoning = reasoning
    choice = mock.MagicMock()
    choice.message = message
    result = mock.MagicMock()
    result.choices = [choice]
    return result


def _patch_openrouter(*side_effect: object):
    client = mock.MagicMock()
    client.chat.send.side_effect = list(side_effect)
    or_cls = mock.MagicMock()
    or_cls.return_value.__enter__.return_value = client
    return mock.patch.object(openrouter_client, "OpenRouter", or_cls), client


class _FakeRateLimit(openrouter_client.errors.TooManyRequestsResponseError):
    def __init__(self) -> None:
        Exception.__init__(self, "rate limited")


_MESSAGES = [{"role": "user", "content": "hi"}]


def test_models_default_when_no_override():
    assert openrouter_client.models() == openrouter_client.DEFAULT_MODELS


def test_models_override_from_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "model-a, model-b ,")
    assert openrouter_client.models() == ("model-a", "model-b")


def test_message_text_prefers_content():
    assert openrouter_client.message_text(_response(content=" hello ").choices[0].message) == "hello"


def test_message_text_falls_back_to_reasoning():
    message = _response(content="", reasoning=" thinking ").choices[0].message
    assert openrouter_client.message_text(message) == "thinking"


def test_missing_api_key_returns_none_without_instantiating_sdk(monkeypatch, caplog):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with (
        mock.patch.object(openrouter_client, "OpenRouter") as or_cls,
        caplog.at_level(logging.WARNING, logger="untappd_pairing.openrouter_client"),
    ):
        result = openrouter_client.complete(_MESSAGES, max_tokens=100)

    assert result is None
    or_cls.assert_not_called()
    assert any("OPENROUTER_API_KEY" in record.message for record in caplog.records)


def test_complete_returns_message_text():
    patch_cm, _client = _patch_openrouter(_response(content="the answer"))
    with patch_cm:
        assert openrouter_client.complete(_MESSAGES, max_tokens=100) == "the answer"


def test_send_receives_expected_args():
    patch_cm, client = _patch_openrouter(_response(content="ok"))
    with patch_cm:
        openrouter_client.complete(_MESSAGES, max_tokens=321)

    kwargs = client.chat.send.call_args.kwargs
    assert kwargs["temperature"] == 0
    assert kwargs["stream"] is False
    assert kwargs["max_tokens"] == 321
    assert kwargs["messages"] is _MESSAGES


def test_sdk_error_on_first_model_falls_back_to_second():
    patch_cm, client = _patch_openrouter(
        openrouter_client.errors.NoResponseError(),
        _response(content="second model answer"),
    )
    with patch_cm:
        result = openrouter_client.complete(_MESSAGES, max_tokens=100)
    assert result == "second model answer"
    assert client.chat.send.call_count == 2


def test_sdk_error_on_all_models_returns_none(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "model-a,model-b")
    patch_cm, client = _patch_openrouter(
        openrouter_client.errors.NoResponseError(),
        openrouter_client.errors.NoResponseError(),
    )
    with patch_cm:
        result = openrouter_client.complete(_MESSAGES, max_tokens=100)
    assert result is None
    assert client.chat.send.call_count == 2


def test_rate_limit_retries_same_model_then_succeeds():
    patch_cm, client = _patch_openrouter(_FakeRateLimit(), _response(content="recovered"))
    with patch_cm, mock.patch.object(openrouter_client.time, "sleep") as sleep_mock:
        result = openrouter_client.complete(_MESSAGES, max_tokens=100)
    assert result == "recovered"
    assert client.chat.send.call_count == 2
    sleep_mock.assert_called_once()


def test_permanent_error_is_not_retried(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "only-model")
    patch_cm, client = _patch_openrouter(openrouter_client.errors.NoResponseError())
    with patch_cm, mock.patch.object(openrouter_client.time, "sleep") as sleep_mock:
        result = openrouter_client.complete(_MESSAGES, max_tokens=100)
    assert result is None
    assert client.chat.send.call_count == 1
    sleep_mock.assert_not_called()
