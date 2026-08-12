from unittest import mock

import pytest

from untappd_pairing import describe
from untappd_pairing.tap_api import TapBeer
from untappd_pairing.untappd_search import UntappdCandidate


def _beer(name="Summer Ale", brewery="Falkon", style="IPA", abv=5.2, degree_plato=12.0):
    return TapBeer(name=name, brewery=brewery, style=style, abv=abv, degree_plato=degree_plato, source="beerstreet")


def _candidate(name="Summer Ale", brewery="Falkon", url="https://untappd.com/b/x/1", rating=3.87):
    return UntappdCandidate(name=name, brewery=brewery, url=url, rating=rating)


def _patch_complete(return_value):
    return mock.patch.object(describe.openrouter_client, "complete", return_value=return_value)


def test_returns_cleaned_description():
    with _patch_complete('  "Svěží IPA s výraznou hořkostí,\n  citrusovým aroma a suchým závěrem."  '):
        result = describe.generate(_beer(), _candidate())
    assert result == "Svěží IPA s výraznou hořkostí, citrusovým aroma a suchým závěrem."


def test_returns_none_when_llm_unavailable():
    with _patch_complete(None):
        assert describe.generate(_beer(), _candidate()) is None


def test_returns_none_for_empty_text():
    with _patch_complete("   "):
        assert describe.generate(_beer(), _candidate()) is None


_VALID = "Klasický světlý ležák se sladovým základem, jemnou hořkostí a lehčím tělem."


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        (_VALID, None),
        ("11° ležák: sladový základ, jemná hořkost a čistá, dopíjivá chuť.", None),
        ("Světlá jedenáctka.", "too short"),
        ("We need to produce a description in Czech based only on the given data, 1-2 sentences.", "no Czech letters"),
        (
            "Popis: Klasický světlý ležák se sladovým základem a jemnou chmelovou hořkostí v závěru.",
            "model talking about the task",
        ),
        (
            "ležák se sladovým základem, jemnou chmelovou hořkostí a čistou, dopíjivou chutí.",
            "starts mid-sentence",
        ),
        (
            "Klasický světlý ležák se sladovým základem a jemnou chmelovou hořkostí v závěru",
            "not a finished sentence",
        ),
    ],
)
def test_rejection_reason(text, reason):
    assert describe.rejection_reason(text) == reason


def test_rejects_invalid_description_after_every_attempt():
    with _patch_complete("We need to produce a Czech description of at most 300 characters here.") as complete:
        assert describe.generate(_beer(), _candidate()) is None
    assert complete.call_count == describe.MAX_ATTEMPTS


def test_retry_feeds_the_rejected_answer_back():
    bad = "We need to produce a Czech description of at most 300 characters here."
    with mock.patch.object(describe.openrouter_client, "complete", side_effect=[bad, _VALID]) as complete:
        assert describe.generate(_beer(), _candidate()) == _VALID

    retry_messages = complete.call_args_list[1].args[0]
    assert retry_messages[-2] == {"role": "assistant", "content": bad}
    assert retry_messages[-1]["content"] == describe.RETRY_PROMPT


def test_refusal_is_not_retried():
    with _patch_complete("NELZE") as complete:
        assert describe.generate(_beer(style=""), _candidate()) is None
    assert complete.call_count == 1


def test_unavailable_llm_is_not_retried():
    with _patch_complete(None) as complete:
        assert describe.generate(_beer(), _candidate()) is None
    assert complete.call_count == 1


def test_truncates_overlong_text():
    with _patch_complete("Svěží IPA s výraznou hořkostí. " * 20):
        result = describe.generate(_beer(), _candidate())
    assert result is not None
    assert len(result) == describe.MAX_CHARS
    assert result.endswith("…")


def test_prompt_includes_beer_facts():
    with _patch_complete("popis") as complete:
        describe.generate(
            _beer(name="Summer Ale", brewery="Falkon", style="West Coast IPA", abv=6.2, degree_plato=13.0),
            _candidate(name="Summer Ale", brewery="Falkon Brewery", rating=3.87),
        )

    messages = complete.call_args.args[0]
    prompt = "\n".join(m["content"] for m in messages)
    assert "Summer Ale" in prompt
    assert "West Coast IPA" in prompt
    assert "13°" in prompt
    assert "6.2 % ABV" in prompt
    assert "3.87 / 5" in prompt


def test_returns_none_for_sentinel():
    with _patch_complete("NELZE"):
        assert describe.generate(_beer(style=""), _candidate()) is None


def test_returns_none_for_dressed_up_sentinel():
    with _patch_complete("Nelze popsat na základě zadaných údajů."):
        assert describe.generate(_beer(style=""), _candidate()) is None


def test_prompt_includes_tap_name_when_it_differs():
    with _patch_complete("popis") as complete:
        describe.generate(_beer(name="Moves"), _candidate(name="Moves - White Grapes and Strawberries"))

    prompt = "\n".join(m["content"] for m in complete.call_args.args[0])
    assert "Název na výčepu: Moves" in prompt
    assert "Moves - White Grapes and Strawberries" in prompt


def test_prompt_omits_tap_name_when_identical():
    with _patch_complete("popis") as complete:
        describe.generate(_beer(name="Summer Ale"), _candidate(name="Summer Ale"))

    prompt = "\n".join(m["content"] for m in complete.call_args.args[0])
    assert "Název na výčepu" not in prompt


def test_uses_max_tokens_budget():
    with _patch_complete("popis") as complete:
        describe.generate(_beer(), _candidate())
    assert complete.call_args.kwargs["max_tokens"] == describe.MAX_TOKENS


def test_disables_reasoning():
    with _patch_complete("popis") as complete:
        describe.generate(_beer(), _candidate())
    assert complete.call_args.kwargs["reasoning"] is False
