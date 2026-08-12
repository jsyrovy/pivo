import json

import pytest

from maintenance import audit_descriptions
from untappd_pairing.store import PairingsStore

_GOOD = "Klasický světlý ležák se sladovým základem, jemnou hořkostí a lehčím tělem."
_BAD = "We need to produce a Czech description of at most 300 characters here."


def _write_pairings(tmp_path, descriptions):
    path = tmp_path / "pairings.json"
    store = PairingsStore()
    for key, description in descriptions.items():
        store.pairings[key] = {"untappd_url": "https://untappd.com/b/x/1", "description": description}
    store.save(path)
    return path


def test_finds_only_suspect_descriptions(tmp_path):
    store = PairingsStore.load(_write_pairings(tmp_path, {"a::b::good": _GOOD, "a::b::bad": _BAD}))
    store.pairings["a::b::none"] = {"untappd_url": "https://untappd.com/b/x/2"}

    assert audit_descriptions.find_suspect_descriptions(store) == [("a::b::bad", "no Czech letters", _BAD)]


@pytest.mark.parametrize(
    ("descriptions", "exit_code"),
    [({"a::b::good": _GOOD}, 0), ({"a::b::good": _GOOD, "a::b::bad": _BAD}, 1)],
)
def test_exit_code_reports_whether_anything_is_suspect(tmp_path, descriptions, exit_code):
    path = _write_pairings(tmp_path, descriptions)
    before = path.read_text(encoding="utf-8")

    assert audit_descriptions.main(["--path", str(path)]) == exit_code
    assert path.read_text(encoding="utf-8") == before


def test_reports_the_offending_key(tmp_path, caplog):
    path = _write_pairings(tmp_path, {"a::b::good": _GOOD, "a::b::bad": _BAD})

    with caplog.at_level("WARNING"):
        audit_descriptions.main(["--path", str(path)])

    assert any("a::b::bad" in record.getMessage() for record in caplog.records)


def test_drop_removes_only_the_suspect_description(tmp_path):
    path = _write_pairings(tmp_path, {"a::b::good": _GOOD, "a::b::bad": _BAD})

    assert audit_descriptions.main(["--path", str(path), "--drop"]) == 0

    pairings = json.loads(path.read_text(encoding="utf-8"))["pairings"]
    assert pairings["a::b::good"]["description"] == _GOOD
    assert "description" not in pairings["a::b::bad"]
    # No cooldown marker, so the next pairing run regenerates it.
    assert "description_failed_at" not in pairings["a::b::bad"]
