import json
import logging

from maintenance import rewrite_brewery_keys

_OLD = "uzamastilu::Sour Madcat::Cherry n' Apricot"
_NEW = "uzamastilu::Madcat::Cherry n' Apricot"


def _write(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_rewritten_key_moves_only_listed_breweries():
    assert rewrite_brewery_keys.rewritten_key(_OLD) == _NEW
    assert rewrite_brewery_keys.rewritten_key("beerstreet::Sour Madcat::Cherry n' Apricot") is None
    assert rewrite_brewery_keys.rewritten_key("ambasada::Clock, Potštejn::A::B") is None


def test_rewrite_keys_keeps_order_and_values(caplog):
    caplog.set_level(logging.INFO)
    entries = {"b::x::y": 1, _OLD: 2, "a::x::y": 3}

    assert list(rewrite_brewery_keys.rewrite_keys(entries, "test").items()) == [
        ("b::x::y", 1),
        (_NEW, 2),
        ("a::x::y", 3),
    ]
    assert f"test: {_OLD} -> {_NEW}" in caplog.text


def test_rewrite_keys_never_overwrites_an_existing_key(caplog):
    entries = {_OLD: "old", _NEW: "new"}

    assert rewrite_brewery_keys.rewrite_keys(entries, "test") == {_OLD: "old", _NEW: "new"}
    assert f"{_NEW} already exists, keeping {_OLD} as is" in caplog.text


def test_rewrite_keys_resolves_two_old_keys_with_one_target_to_the_first():
    first = "uzamastilu::NZ Hazy Ale Klenot::Rhapsody Of Fog"
    second = "uzamastilu::NZ Hazy IPA Klenot::Rhapsody Of Fog"

    result = rewrite_brewery_keys.rewrite_keys({first: 1, second: 2}, "test")

    assert result == {"uzamastilu::Klenot::Rhapsody Of Fog": 1, second: 2}


def test_main_rewrites_all_three_files(tmp_path):
    pairings = _write(
        tmp_path / "pairings.json",
        {
            "version": 1,
            "generated_at": "2026-09-10T19:31:54Z",
            "pairings": {_OLD: {"untappd_url": "u"}, "a::b::c": {"untappd_url": "v"}},
            "unmatched": {"uzamastilu::Pastry Sour Twinberg::Brew Berrymode": {"attempts": 1}},
        },
    )
    overrides = _write(tmp_path / "overrides.json", {"z::z::z": "w", "uzamastilu::Pale Ale Brewnicorn::Hoppla!": "x"})
    fixtures = _write(
        tmp_path / "fixtures.json",
        {
            "version": 1,
            "fixtures": {
                _OLD: {"beer": {"brewery": "Sour Madcat", "name": "Cherry n' Apricot"}},
                "x::y::z": {"annotation": None},
            },
        },
    )

    assert (
        rewrite_brewery_keys.main(
            ["--pairings", str(pairings), "--overrides", str(overrides), "--fixtures", str(fixtures)],
        )
        == 0
    )

    assert _read(pairings) == {
        "version": 1,
        "generated_at": "2026-09-10T19:31:54Z",
        "pairings": {"a::b::c": {"untappd_url": "v"}, _NEW: {"untappd_url": "u"}},
        "unmatched": {"uzamastilu::Twinberg::Brew Berrymode": {"attempts": 1}},
    }
    assert list(_read(overrides)) == ["z::z::z", "uzamastilu::Brewnicorn::Hoppla!"]
    assert _read(fixtures) == {
        "version": 1,
        "fixtures": {
            _NEW: {"beer": {"brewery": "Madcat", "name": "Cherry n' Apricot"}},
            "x::y::z": {"annotation": None},
        },
    }


def test_main_tolerates_missing_files(tmp_path):
    paths = [tmp_path / name for name in ("pairings.json", "overrides.json", "fixtures.json")]

    rewrite_brewery_keys.main(
        ["--pairings", str(paths[0]), "--overrides", str(paths[1]), "--fixtures", str(paths[2])],
    )

    assert _read(paths[0]) == {"pairings": {}, "unmatched": {}}
    assert _read(paths[1]) == {}
    assert _read(paths[2]) == {"fixtures": {}}
