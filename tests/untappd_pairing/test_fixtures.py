import json
from datetime import UTC, datetime

import pytest

from untappd_pairing.fixtures import (
    SCHEMA_VERSION,
    FixtureAnnotation,
    FixtureOutcome,
    FixturesStore,
    compress_url,
    expand_url,
    expected_outcome,
    replay,
)
from untappd_pairing.store import beer_key
from untappd_pairing.tap_api import TapBeer
from untappd_pairing.untappd_search import UntappdCandidate


def _beer(name="Tears of St Laurent (2020)", brewery="Wild Creatures", source="beerstreet", degree_plato=None):
    return TapBeer(
        name=name,
        brewery=brewery,
        style="Sour",
        abv=6.0,
        degree_plato=degree_plato,
        source=source,
    )


def _candidate(name="Tears of St Laurent (2020)", brewery="Wild Creatures", url_path="/b/wild-tears/1", rating=4.1):
    return UntappdCandidate(name=name, brewery=brewery, url=f"https://untappd.com{url_path}", rating=rating)


def test_compress_and_expand_url_roundtrip():
    full = "https://untappd.com/b/wild-tears/1"
    assert compress_url(full) == "/b/wild-tears/1"
    assert expand_url("/b/wild-tears/1") == full


def test_compress_url_leaves_unknown_hosts_alone():
    other = "https://other-site.com/b/x/1"
    assert compress_url(other) == other


@pytest.mark.parametrize(
    ("matched_url", "reason"),
    [(None, None), ("/b/x/1", "no_candidates_above_threshold")],
)
def test_fixture_outcome_rejects_invalid_state(matched_url, reason):
    with pytest.raises(ValueError, match="exactly one"):
        FixtureOutcome(matched_url=matched_url, reason=reason)


def test_expand_url_leaves_absolute_urls_alone():
    other = "https://other-site.com/b/x/1"
    assert expand_url(other) == other


def test_load_returns_empty_when_file_missing(tmp_path):
    store = FixturesStore.load(tmp_path / "missing.json")
    assert store.records == {}


def test_upsert_dedups_candidates_across_attempts():
    store = FixturesStore()
    beer = _beer()
    cand_a = _candidate(name="Tears A", url_path="/b/a/1")
    cand_b = _candidate(name="Tears B", url_path="/b/b/2")

    store.upsert(
        beer,
        attempts=[("query one", [cand_a, cand_b]), ("query two", [cand_b])],
        outcome=FixtureOutcome(matched_url="/b/a/1", score=0.9),
    )

    record = store.records[beer_key(beer.source, beer.brewery, beer.name)]
    assert [c.url for c in record.candidates] == ["/b/a/1", "/b/b/2"]
    assert record.attempts[0].hits == (0, 1)
    assert record.attempts[1].hits == (1,)


def test_upsert_preserves_annotation_when_re_capturing():
    store = FixturesStore()
    beer = _beer()
    cand = _candidate()

    store.upsert(
        beer,
        attempts=[("q1", [cand])],
        outcome=FixtureOutcome(matched_url="/b/wild-tears/1", score=0.8),
    )
    key = beer_key(beer.source, beer.brewery, beer.name)
    store.records[key].annotation = FixtureAnnotation(verdict="wrong_match", expected_url="/b/right/2", note="bad")

    store.upsert(
        beer,
        attempts=[("q1", [cand]), ("q2", [cand])],
        outcome=FixtureOutcome(matched_url="/b/wild-tears/1", score=0.95),
    )

    annotation = store.records[key].annotation
    assert annotation is not None
    assert annotation.verdict == "wrong_match"
    assert annotation.expected_url == "/b/right/2"


def test_save_and_load_roundtrip_with_annotation(tmp_path):
    path = tmp_path / "fixtures.json"
    store = FixturesStore()
    beer = _beer(degree_plato=11)
    cand = _candidate()

    store.upsert(
        beer,
        attempts=[("q1", [cand])],
        outcome=FixtureOutcome(matched_url="/b/wild-tears/1", score=0.9),
        now=datetime(2026, 5, 22, 12, 0, tzinfo=UTC),
    )
    key = beer_key(beer.source, beer.brewery, beer.name)
    store.records[key].annotation = FixtureAnnotation(
        verdict="wrong_match",
        expected_url="/b/right/2",
        note="should pick /b/right/2",
    )
    store.save(path, now=datetime(2026, 5, 22, 12, 0, tzinfo=UTC))

    raw = json.loads(path.read_text())
    assert raw["version"] == SCHEMA_VERSION
    assert raw["generated_at"] == "2026-05-22T12:00:00Z"
    entry = raw["fixtures"][key]
    assert entry["beer"]["degree_plato"] == 11
    assert entry["candidates"][0]["url"] == "/b/wild-tears/1"
    assert entry["outcome"] == {"matched": "/b/wild-tears/1", "score": 0.9}
    assert entry["annotation"]["verdict"] == "wrong_match"

    reloaded = FixturesStore.load(path)
    reloaded_record = reloaded.records[key]
    assert reloaded_record.outcome.matched_url == "/b/wild-tears/1"
    assert reloaded_record.annotation is not None
    assert reloaded_record.annotation.verdict == "wrong_match"


def test_save_serializes_unmatched_outcome_without_score(tmp_path):
    path = tmp_path / "fixtures.json"
    store = FixturesStore()
    beer = _beer(name="Mystery", brewery="Unknown")
    store.upsert(
        beer,
        attempts=[("q1", [])],
        outcome=FixtureOutcome(matched_url=None, reason="no_candidates_above_threshold"),
    )
    store.save(path)

    raw = json.loads(path.read_text())
    entry = raw["fixtures"][beer_key(beer.source, beer.brewery, beer.name)]
    assert entry["outcome"] == {"matched": None, "reason": "no_candidates_above_threshold"}


def test_save_sorts_keys_for_stable_diffs(tmp_path):
    path = tmp_path / "fixtures.json"
    store = FixturesStore()
    store.upsert(_beer(name="Zeta"), attempts=[("q", [])], outcome=FixtureOutcome(matched_url=None, reason="x"))
    store.upsert(_beer(name="Alpha"), attempts=[("q", [])], outcome=FixtureOutcome(matched_url=None, reason="x"))
    store.save(path)

    keys = list(json.loads(path.read_text())["fixtures"].keys())
    assert keys == sorted(keys)


def test_load_recovers_from_corrupt_file(tmp_path, caplog):
    path = tmp_path / "fixtures.json"
    path.write_text("not json at all")
    with caplog.at_level("ERROR"):
        store = FixturesStore.load(path)
    assert store.records == {}


def test_load_skips_non_dict_entries_in_fixtures_map(tmp_path):
    path = tmp_path / "fixtures.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "fixtures": {
                    "garbage": "not a dict",
                    "beerstreet::X::Y": {
                        "beer": {
                            "source": "beerstreet",
                            "brewery": "X",
                            "name": "Y",
                            "style": "",
                            "degree_plato": None,
                        },
                        "candidates": [],
                        "attempts": [],
                        "outcome": {"matched": None, "reason": "no_candidates_above_threshold"},
                    },
                },
            },
        ),
    )
    store = FixturesStore.load(path)
    assert list(store.records.keys()) == ["beerstreet::X::Y"]


def test_load_drops_record_with_missing_required_field(tmp_path, caplog):
    path = tmp_path / "fixtures.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "fixtures": {
                    "beerstreet::X::Y": {
                        "beer": {"brewery": "X", "name": "Y"},  # missing 'source'
                        "candidates": [],
                        "attempts": [],
                        "outcome": {"matched": None, "reason": "x"},
                    },
                },
            },
        ),
    )
    with caplog.at_level("ERROR"):
        store = FixturesStore.load(path)
    assert store.records == {}


def test_load_drops_annotation_with_invalid_verdict(tmp_path, caplog):
    path = tmp_path / "fixtures.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "fixtures": {
                    "beerstreet::X::Y": {
                        "beer": {
                            "source": "beerstreet",
                            "brewery": "X",
                            "name": "Y",
                            "style": "",
                            "degree_plato": None,
                        },
                        "candidates": [],
                        "attempts": [],
                        "outcome": {"matched": None, "reason": "no_candidates_above_threshold"},
                        "annotation": {"verdict": "bogus", "expected": None, "note": ""},
                    },
                },
            },
        ),
    )
    with caplog.at_level("ERROR"):
        store = FixturesStore.load(path)
    record = store.records["beerstreet::X::Y"]
    assert record.annotation is None


def _record_with(
    outcome,
    *,
    attempts_candidates=(("q1", []),),
    annotation=None,
    beer_kwargs=None,
):
    store = FixturesStore()
    beer = _beer(**(beer_kwargs or {}))
    store.upsert(beer, attempts=list(attempts_candidates), outcome=outcome)
    key = beer_key(beer.source, beer.brewery, beer.name)
    record = store.records[key]
    record.annotation = annotation
    return record


def test_replay_returns_url_of_first_matching_attempt():
    cand = _candidate(name="Tears of St Laurent (2020)", brewery="Wild Creatures", url_path="/b/wild-tears/1")
    record = _record_with(
        FixtureOutcome(matched_url="/b/wild-tears/1", score=1.0),
        attempts_candidates=[("q1", []), ("q2", [cand])],
    )

    assert replay(record) == "/b/wild-tears/1"


def test_replay_returns_none_when_no_attempt_matches():
    record = _record_with(
        FixtureOutcome(matched_url=None, reason="no_candidates_above_threshold"),
        attempts_candidates=[("q1", [])],
    )

    assert replay(record) is None


def test_expected_outcome_without_annotation_uses_recorded_outcome():
    record = _record_with(FixtureOutcome(matched_url="/b/wild-tears/1", score=0.9))
    result = expected_outcome(record)
    assert result is not None
    assert result.matched_url == "/b/wild-tears/1"


def test_expected_outcome_uses_annotation_expected_for_wrong_match():
    record = _record_with(
        FixtureOutcome(matched_url="/b/wrong/1", score=0.9),
        annotation=FixtureAnnotation(verdict="wrong_match", expected_url="/b/right/2"),
    )
    result = expected_outcome(record)
    assert result is not None
    assert result.matched_url == "/b/right/2"


def test_expected_outcome_uses_annotation_expected_for_should_match():
    record = _record_with(
        FixtureOutcome(matched_url=None, reason="no_candidates_above_threshold"),
        annotation=FixtureAnnotation(verdict="should_match", expected_url="/b/right/2"),
    )
    result = expected_outcome(record)
    assert result is not None
    assert result.matched_url == "/b/right/2"


def test_expected_outcome_for_not_on_untappd_expects_no_match():
    record = _record_with(
        FixtureOutcome(matched_url=None, reason="no_candidates_above_threshold"),
        annotation=FixtureAnnotation(verdict="not_on_untappd"),
    )
    result = expected_outcome(record)
    assert result is not None
    assert result.matched_url is None


def test_expected_outcome_returns_none_for_expected_missing():
    record = _record_with(
        FixtureOutcome(matched_url=None, reason="no_candidates_above_threshold"),
        annotation=FixtureAnnotation(verdict="expected_missing", expected_url="/b/never-returned/9"),
    )
    assert expected_outcome(record) is None
