import logging
from unittest import mock

from untappd_pairing import llm_matcher
from untappd_pairing.tap_api import TapBeer
from untappd_pairing.untappd_search import UntappdCandidate


def _beer(name="Summer Ale", brewery="Kynšperský zajíc", degree_plato=None):
    return TapBeer(name=name, brewery=brewery, style="Ale", abv=None, degree_plato=degree_plato, source="beerstreet")


def _candidate(name, brewery="Kynšperský pivovar", url="https://untappd.com/b/x/1", rating=4.0):
    return UntappdCandidate(name=name, brewery=brewery, url=url, rating=rating)


def _patch_complete(return_value):
    return mock.patch.object(llm_matcher.openrouter_client, "complete", return_value=return_value)


def test_no_candidates_returns_none_without_calling_llm():
    with _patch_complete('{"index": 0}') as complete:
        assert llm_matcher.adjudicate(_beer(), []) is None
    complete.assert_not_called()


def test_valid_index_returns_candidate():
    candidates = [
        _candidate("Wrong Beer", url="https://untappd.com/b/x/1"),
        _candidate("Summer Ale", url="https://untappd.com/b/x/2"),
    ]
    with _patch_complete('{"index": 1}'):
        result = llm_matcher.adjudicate(_beer(), candidates)
    assert result is candidates[1]


def test_index_null_returns_none():
    with _patch_complete('{"index": null, "reasoning": "no match"}'):
        result = llm_matcher.adjudicate(_beer(), [_candidate("Summer Ale")])
    assert result is None


def test_index_out_of_range_returns_none():
    with _patch_complete('{"index": 5}'):
        result = llm_matcher.adjudicate(_beer(), [_candidate("Summer Ale")])
    assert result is None


def test_malformed_reply_returns_none():
    with _patch_complete("I cannot answer that."):
        result = llm_matcher.adjudicate(_beer(), [_candidate("Summer Ale")])
    assert result is None


def test_json_buried_at_end_of_reasoning_stream_is_parsed():
    candidates = [_candidate("Wrong"), _candidate("Summer Ale", url="https://untappd.com/b/x/2")]
    text = (
        "Let me think. The first candidate is a different beer. "
        'The second matches. {"index": 0} was my first guess but actually {"index": 1}'
    )
    with _patch_complete(text):
        result = llm_matcher.adjudicate(_beer(), candidates)
    assert result is candidates[1]


def test_llm_unavailable_returns_none(caplog):
    with (
        _patch_complete(None),
        caplog.at_level(logging.WARNING, logger="untappd_pairing.llm_matcher"),
    ):
        result = llm_matcher.adjudicate(_beer(), [_candidate("Summer Ale")])
    assert result is None
    assert any("unavailable" in record.message for record in caplog.records)


def test_prompt_contains_beer_and_candidate_details():
    candidates = [_candidate("Summer Ale", brewery="Kynšperský pivovar")]
    with _patch_complete('{"index": 0}') as complete:
        llm_matcher.adjudicate(_beer(name="Summer Ale", brewery="Kynšperský zajíc"), candidates)

    messages = complete.call_args.args[0]
    prompt = "\n".join(m["content"] for m in messages)
    assert "Summer Ale" in prompt
    assert "Kynšperský zajíc" in prompt
    assert "Kynšperský pivovar" in prompt
