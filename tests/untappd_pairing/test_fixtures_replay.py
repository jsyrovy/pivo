from pathlib import Path

import pytest

from untappd_pairing.fixtures import FIXTURES_PATH, FixtureRecord, FixturesStore, expected_outcome, replay


def _load_records() -> list[tuple[str, FixtureRecord]]:
    path = Path(FIXTURES_PATH)
    if not path.exists():
        return []
    store = FixturesStore.load(path)
    return list(store.records.items())


@pytest.mark.parametrize(("key", "record"), _load_records())
def test_replay_matches_expected_outcome(key, record):
    expected = expected_outcome(record)
    if expected is None:
        pytest.skip(f"{key}: 'expected_missing' fixtures require fresh search results to replay")
    actual = replay(record)
    assert actual == expected.matched_url, (
        f"{key}: replay produced {actual!r}, expected {expected.matched_url!r} ({expected.reason})"
    )
