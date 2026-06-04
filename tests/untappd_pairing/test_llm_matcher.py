import logging
from unittest import mock

import pytest

from untappd_pairing import llm_matcher
from untappd_pairing.tap_api import TapBeer
from untappd_pairing.untappd_search import UntappdCandidate


@pytest.fixture(autouse=True)
def _api_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)


def _beer(name="Summer Ale", brewery="Kynšperský zajíc", degree_plato=None):
    return TapBeer(name=name, brewery=brewery, style="Ale", abv=None, degree_plato=degree_plato, source="beerstreet")


def _candidate(name, brewery="Kynšperský pivovar", url="https://untappd.com/b/x/1", rating=4.0):
    return UntappdCandidate(name=name, brewery=brewery, url=url, rating=rating)


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
    """Patch llm_matcher.OpenRouter with a context-manager mock; return (patch_cm, client_mock)."""
    client = mock.MagicMock()
    client.chat.send.side_effect = list(side_effect)
    or_cls = mock.MagicMock()
    or_cls.return_value.__enter__.return_value = client
    return mock.patch.object(llm_matcher, "OpenRouter", or_cls), client


class _FakeRateLimit(llm_matcher.errors.TooManyRequestsResponseError):
    def __init__(self) -> None:
        Exception.__init__(self, "rate limited")


def test_missing_api_key_returns_none_without_instantiating_sdk(monkeypatch, caplog):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with (
        mock.patch.object(llm_matcher, "OpenRouter") as or_cls,
        caplog.at_level(logging.WARNING, logger="untappd_pairing.llm_matcher"),
    ):
        result = llm_matcher.adjudicate(_beer(), [_candidate("Summer Ale")])

    assert result is None
    or_cls.assert_not_called()
    assert any("OPENROUTER_API_KEY" in record.message for record in caplog.records)


def test_no_candidates_returns_none():
    with mock.patch.object(llm_matcher, "OpenRouter") as or_cls:
        assert llm_matcher.adjudicate(_beer(), []) is None
    or_cls.assert_not_called()


def test_valid_index_returns_candidate():
    candidates = [
        _candidate("Wrong Beer", url="https://untappd.com/b/x/1"),
        _candidate("Summer Ale", url="https://untappd.com/b/x/2"),
    ]
    patch_cm, _client = _patch_openrouter(_response(content='{"index": 1}'))
    with patch_cm:
        result = llm_matcher.adjudicate(_beer(), candidates)
    assert result is candidates[1]


def test_index_null_returns_none():
    patch_cm, _client = _patch_openrouter(_response(content='{"index": null, "reasoning": "no match"}'))
    with patch_cm:
        result = llm_matcher.adjudicate(_beer(), [_candidate("Summer Ale")])
    assert result is None


def test_index_out_of_range_returns_none():
    patch_cm, _client = _patch_openrouter(_response(content='{"index": 5}'))
    with patch_cm:
        result = llm_matcher.adjudicate(_beer(), [_candidate("Summer Ale")])
    assert result is None


def test_malformed_reply_returns_none():
    patch_cm, _client = _patch_openrouter(_response(content="I cannot answer that."))
    with patch_cm:
        result = llm_matcher.adjudicate(_beer(), [_candidate("Summer Ale")])
    assert result is None


def test_reasoning_model_json_in_reasoning_field():
    # content empty, the final JSON is buried at the end of the reasoning stream.
    candidates = [_candidate("Wrong"), _candidate("Summer Ale", url="https://untappd.com/b/x/2")]
    reasoning = (
        "Let me think. The first candidate is a different beer. "
        'The second matches. {"index": 0} was my first guess but actually {"index": 1}'
    )
    patch_cm, _client = _patch_openrouter(_response(content="", reasoning=reasoning))
    with patch_cm:
        result = llm_matcher.adjudicate(_beer(), candidates)
    assert result is candidates[1]


def test_sdk_error_on_first_model_falls_back_to_second():
    candidates = [_candidate("Summer Ale")]
    patch_cm, client = _patch_openrouter(
        llm_matcher.errors.NoResponseError(),
        _response(content='{"index": 0}'),
    )
    with patch_cm:
        result = llm_matcher.adjudicate(_beer(), candidates)
    assert result is candidates[0]
    assert client.chat.send.call_count == 2


def test_sdk_error_on_all_models_returns_none(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "model-a,model-b")
    patch_cm, client = _patch_openrouter(
        llm_matcher.errors.NoResponseError(),
        llm_matcher.errors.NoResponseError(),
    )
    with patch_cm:
        result = llm_matcher.adjudicate(_beer(), [_candidate("Summer Ale")])
    assert result is None
    assert client.chat.send.call_count == 2


def test_rate_limit_retries_same_model_then_succeeds():
    candidates = [_candidate("Summer Ale")]
    patch_cm, client = _patch_openrouter(_FakeRateLimit(), _response(content='{"index": 0}'))
    with patch_cm, mock.patch.object(llm_matcher.time, "sleep") as sleep_mock:
        result = llm_matcher.adjudicate(_beer(), candidates)
    assert result is candidates[0]
    assert client.chat.send.call_count == 2
    sleep_mock.assert_called_once()


def test_permanent_error_is_not_retried(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "only-model")
    patch_cm, client = _patch_openrouter(llm_matcher.errors.NoResponseError())
    with patch_cm, mock.patch.object(llm_matcher.time, "sleep") as sleep_mock:
        result = llm_matcher.adjudicate(_beer(), [_candidate("Summer Ale")])
    assert result is None
    assert client.chat.send.call_count == 1
    sleep_mock.assert_not_called()


def test_send_receives_expected_args_and_prompt():
    candidates = [_candidate("Summer Ale", brewery="Kynšperský pivovar")]
    patch_cm, client = _patch_openrouter(_response(content='{"index": 0}'))
    with patch_cm:
        llm_matcher.adjudicate(_beer(name="Summer Ale", brewery="Kynšperský zajíc"), candidates)

    kwargs = client.chat.send.call_args.kwargs
    assert kwargs["temperature"] == 0
    assert kwargs["stream"] is False
    prompt = "\n".join(m["content"] for m in kwargs["messages"])
    assert "Summer Ale" in prompt
    assert "Kynšperský zajíc" in prompt
    assert "Kynšperský pivovar" in prompt
