import json

from maintenance import audit_descriptions

_GOOD = "Klasický světlý ležák se sladovým základem, jemnou hořkostí a lehčím tělem."
_BAD = "We need to produce a Czech description of at most 300 characters here."


def _write_pairings(tmp_path, descriptions):
    path = tmp_path / "pairings.json"
    pairings = {
        key: {"untappd_url": f"https://untappd.com/b/x/{index}", "description": description}
        for index, (key, description) in enumerate(descriptions.items())
    }
    path.write_text(json.dumps({"version": 1, "pairings": pairings}), encoding="utf-8")
    return path


def test_finds_only_suspect_descriptions():
    pairings = {
        "a::b::good": {"description": _GOOD},
        "a::b::bad": {"description": _BAD},
        "a::b::none": {},
    }
    assert audit_descriptions.find_suspect_descriptions(pairings) == [("a::b::bad", "no Czech letters")]


def test_reports_without_changing_the_file(tmp_path, caplog):
    path = _write_pairings(tmp_path, {"a::b::good": _GOOD, "a::b::bad": _BAD})
    before = path.read_text(encoding="utf-8")

    with caplog.at_level("WARNING"):
        exit_code = audit_descriptions.main(["--path", str(path)])

    assert exit_code == 1
    assert path.read_text(encoding="utf-8") == before
    assert any("a::b::bad" in record.getMessage() for record in caplog.records)


def test_drop_removes_only_the_suspect_description(tmp_path):
    path = _write_pairings(tmp_path, {"a::b::good": _GOOD, "a::b::bad": _BAD})

    assert audit_descriptions.main(["--path", str(path), "--drop"]) == 0

    pairings = json.loads(path.read_text(encoding="utf-8"))["pairings"]
    assert pairings["a::b::good"]["description"] == _GOOD
    assert "description" not in pairings["a::b::bad"]
    assert pairings["a::b::bad"]["untappd_url"]


def test_clean_store_exits_zero(tmp_path):
    path = _write_pairings(tmp_path, {"a::b::good": _GOOD})
    assert audit_descriptions.main(["--path", str(path)]) == 0
