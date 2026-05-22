import json
from datetime import UTC, datetime, timedelta

import pytest

from untappd_pairing.matcher import MatchResult
from untappd_pairing.store import RETRY_AFTER, SCHEMA_VERSION, PairingsStore, beer_key
from untappd_pairing.tap_api import TapBeer
from untappd_pairing.untappd_search import UntappdCandidate


def _beer(name="IPA", brewery="Falkon", source="beerstreet"):
    return TapBeer(name=name, brewery=brewery, style="", abv=None, degree_plato=None, source=source)


def _candidate():
    return UntappdCandidate(
        name="IPA",
        brewery="Falkon",
        url="https://untappd.com/b/falkon-ipa/1",
        rating=4.1,
    )


def test_load_returns_empty_when_file_missing(tmp_path):
    store = PairingsStore.load(tmp_path / "missing.json")
    assert store.pairings == {}
    assert store.unmatched == {}


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "pairings.json"
    store = PairingsStore()
    now = datetime(2026, 4, 17, 19, 0, tzinfo=UTC)
    store.record_match(_beer(), MatchResult(candidate=_candidate(), score=0.92), "IPA Falkon", now=now)
    store.save(path, now=now)

    raw = json.loads(path.read_text())
    assert raw["version"] == SCHEMA_VERSION
    assert raw["generated_at"] == "2026-04-17T19:00:00Z"
    assert "beerstreet::Falkon::IPA" in raw["pairings"]
    assert raw["pairings"]["beerstreet::Falkon::IPA"]["query_used"] == "IPA Falkon"

    reloaded = PairingsStore.load(path)
    assert reloaded.pairings == store.pairings


def test_select_pending_re_pairs_when_override_url_differs_from_existing():
    store = PairingsStore()
    beer = _beer(name="Maisels Weisse")
    key = beer_key(beer.source, beer.brewery, beer.name)
    store.pairings[key] = {"untappd_url": "https://untappd.com/b/wrong/1"}

    overrides = {key: "https://untappd.com/b/right/2"}
    pending = store.select_pending([beer], overrides=overrides)

    assert [b.name for b in pending] == ["Maisels Weisse"]


def test_select_pending_skips_overridden_beer_when_already_matched_to_override_url():
    store = PairingsStore()
    beer = _beer(name="Maisels Weisse")
    key = beer_key(beer.source, beer.brewery, beer.name)
    overrides = {key: "https://untappd.com/b/right/2"}
    store.pairings[key] = {"untappd_url": overrides[key]}

    assert store.select_pending([beer], overrides=overrides) == []


def test_select_pending_skips_paired_beers():
    store = PairingsStore()
    paired = _beer(name="Paired")
    unpaired = _beer(name="New")
    store.record_match(paired, MatchResult(candidate=_candidate(), score=0.9), "q")

    pending = store.select_pending([paired, unpaired])
    assert [b.name for b in pending] == ["New"]


def test_select_pending_skips_recently_unmatched_beers():
    store = PairingsStore()
    beer = _beer(name="Hard to find")
    now = datetime(2026, 4, 17, 19, 0, tzinfo=UTC)
    store.record_unmatched(beer, "no_candidates_above_threshold", now=now)

    pending = store.select_pending([beer], now=now + timedelta(days=1))
    assert pending == []


def test_select_pending_retries_upstream_error_immediately():
    store = PairingsStore()
    beer = _beer(name="Flaky API")
    now = datetime(2026, 4, 17, 19, 0, tzinfo=UTC)
    store.record_unmatched(beer, "upstream_error", now=now)

    pending = store.select_pending([beer], now=now + timedelta(minutes=5))
    assert [b.name for b in pending] == ["Flaky API"]


@pytest.mark.parametrize("reason", ["no_candidates_above_threshold", "override_page_parse_failed"])
def test_select_pending_still_skips_recent_non_transient_reasons(reason):
    store = PairingsStore()
    beer = _beer(name="Hard to find")
    now = datetime(2026, 4, 17, 19, 0, tzinfo=UTC)
    store.record_unmatched(beer, reason, now=now)

    pending = store.select_pending([beer], now=now + timedelta(days=1))
    assert pending == []


def test_select_pending_retries_unmatched_after_cooldown():
    store = PairingsStore()
    beer = _beer(name="Hard to find")
    now = datetime(2026, 4, 17, 19, 0, tzinfo=UTC)
    store.record_unmatched(beer, "no_candidates_above_threshold", now=now)

    pending = store.select_pending([beer], now=now + RETRY_AFTER + timedelta(seconds=1))
    assert [b.name for b in pending] == ["Hard to find"]


def test_get_url_returns_matched_untappd_url():
    store = PairingsStore()
    beer = _beer()
    store.record_match(beer, MatchResult(candidate=_candidate(), score=0.95), "q")

    assert store.get_url(beer_key(beer.source, beer.brewery, beer.name)) == "https://untappd.com/b/falkon-ipa/1"


def test_record_match_clears_previous_unmatched_entry():
    store = PairingsStore()
    beer = _beer()
    store.record_unmatched(beer, "no_candidates_above_threshold")
    assert beer_key(beer.source, beer.brewery, beer.name) in store.unmatched

    store.record_match(beer, MatchResult(candidate=_candidate(), score=0.95), "q")
    assert beer_key(beer.source, beer.brewery, beer.name) not in store.unmatched


def test_record_unmatched_increments_attempts():
    store = PairingsStore()
    beer = _beer()
    store.record_unmatched(beer, "no_candidates_above_threshold")
    store.record_unmatched(beer, "no_candidates_above_threshold")

    entry = store.unmatched[beer_key(beer.source, beer.brewery, beer.name)]
    assert entry["attempts"] == 2


def test_save_sorts_keys_for_stable_diffs(tmp_path):
    path = tmp_path / "pairings.json"
    store = PairingsStore()
    now = datetime(2026, 4, 17, 19, 0, tzinfo=UTC)
    store.record_match(_beer(name="Zeta"), MatchResult(candidate=_candidate(), score=0.9), "q1", now=now)
    store.record_match(_beer(name="Alpha"), MatchResult(candidate=_candidate(), score=0.9), "q2", now=now)
    store.save(path, now=now)

    keys = list(json.loads(path.read_text())["pairings"].keys())
    assert keys == sorted(keys)


def test_load_recovers_from_corrupt_file(tmp_path, caplog):
    path = tmp_path / "pairings.json"
    path.write_text("not json at all")
    with caplog.at_level("ERROR"):
        store = PairingsStore.load(path)
    assert store.pairings == {}
    assert store.unmatched == {}
