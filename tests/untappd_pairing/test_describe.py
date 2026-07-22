from unittest import mock

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
    with _patch_complete('  "Svěží IPA s výraznou\n  hořkostí."  '):
        result = describe.generate(_beer(), _candidate())
    assert result == "Svěží IPA s výraznou hořkostí."


def test_returns_none_when_llm_unavailable():
    with _patch_complete(None):
        assert describe.generate(_beer(), _candidate()) is None


def test_returns_none_for_empty_text():
    with _patch_complete("   "):
        assert describe.generate(_beer(), _candidate()) is None


def test_truncates_overlong_text():
    with _patch_complete("A" * 500):
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


def test_uses_max_tokens_budget():
    with _patch_complete("popis") as complete:
        describe.generate(_beer(), _candidate())
    assert complete.call_args.kwargs["max_tokens"] == describe.MAX_TOKENS
