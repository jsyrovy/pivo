import json
import logging
from unittest import mock

import httpx
import pytest

from robot.base import Args
from untappd_pairing import pairing
from untappd_pairing.pairing import UntappdPairing
from untappd_pairing.tap_api import TapBeer
from untappd_pairing.untappd_search import UntappdCandidate


@pytest.fixture(autouse=True)
def mock_pushover():
    with mock.patch.object(pairing.pushover, "send_notification") as m:
        yield m


def _beer(name, brewery="Falkon", degree_plato=None):
    return TapBeer(
        name=name,
        brewery=brewery,
        style="IPA",
        abv=5.0,
        degree_plato=degree_plato,
        source="beerstreet",
    )


def _candidate(name, brewery="Falkon", url="https://untappd.com/b/x/1", rating=4.1):
    return UntappdCandidate(name=name, brewery=brewery, url=url, rating=rating)


def test_pairing_writes_matched_and_unmatched(tmp_path, monkeypatch):
    pairings_path = tmp_path / "pairings.json"
    monkeypatch.setattr(pairing, "PAIRINGS_PATH", pairings_path)

    beers = [_beer("Tears of St Laurent (2020)", "Wild Creatures"), _beer("Mystery Brew", "Unknown")]

    def fake_search(query):
        if "Tears" in query:
            return [_candidate("Tears of St Laurent (2020)", brewery="Wild Creatures")]
        return []

    with (
        mock.patch.object(pairing.tap_api, "fetch_all_beers", return_value=beers),
        mock.patch.object(pairing.untappd_search, "search_beer", side_effect=fake_search),
    ):
        UntappdPairing(args=Args()).run()

    saved = json.loads(pairings_path.read_text())
    assert "beerstreet::Wild Creatures::Tears of St Laurent (2020)" in saved["pairings"]
    assert "beerstreet::Unknown::Mystery Brew" in saved["unmatched"]
    assert saved["unmatched"]["beerstreet::Unknown::Mystery Brew"]["reason"] == "no_candidates_above_threshold"


def test_pairing_skips_already_paired_beers_on_second_run(tmp_path, monkeypatch):
    pairings_path = tmp_path / "pairings.json"
    monkeypatch.setattr(pairing, "PAIRINGS_PATH", pairings_path)

    beer = _beer("Tears of St Laurent (2020)", "Wild Creatures")
    candidates = [_candidate("Tears of St Laurent (2020)", brewery="Wild Creatures")]

    search_mock = mock.Mock(return_value=candidates)

    with (
        mock.patch.object(pairing.tap_api, "fetch_all_beers", return_value=[beer]),
        mock.patch.object(pairing.untappd_search, "search_beer", search_mock),
    ):
        UntappdPairing(args=Args()).run()
        UntappdPairing(args=Args()).run()

    assert search_mock.call_count == 1


def test_pairing_records_upstream_error_on_http_failure(tmp_path, monkeypatch):
    pairings_path = tmp_path / "pairings.json"
    monkeypatch.setattr(pairing, "PAIRINGS_PATH", pairings_path)

    beer = _beer("IPA", "Brewery")

    with (
        mock.patch.object(pairing.tap_api, "fetch_all_beers", return_value=[beer]),
        mock.patch.object(
            pairing.untappd_search,
            "search_beer",
            side_effect=httpx.ConnectError("boom"),
        ),
    ):
        UntappdPairing(args=Args()).run()

    saved = json.loads(pairings_path.read_text())
    entry = saved["unmatched"]["beerstreet::Brewery::IPA"]
    assert entry["reason"] == "upstream_error"


def test_pairing_uses_override_url_and_fetches_beer_page(tmp_path, monkeypatch):
    pairings_path = tmp_path / "pairings.json"
    overrides_path = tmp_path / "overrides.json"
    monkeypatch.setattr(pairing, "PAIRINGS_PATH", pairings_path)
    monkeypatch.setattr(pairing.overrides_module, "OVERRIDES_PATH", overrides_path)

    beer = _beer("Maisels Weisse", "Maisel, Bayreuth, Bavorsko")
    overrides_path.write_text(
        json.dumps({"beerstreet::Maisel, Bayreuth, Bavorsko::Maisels Weisse": "https://untappd.com/b/x/35642"}),
    )

    fetched = UntappdCandidate(
        name="Maisel's Weisse Original",
        brewery="Brauerei Gebr. Maisel",
        url="https://untappd.com/b/x/35642",
        rating=3.59774,
    )

    fetch_mock = mock.Mock(return_value=fetched)
    search_mock = mock.Mock()

    with (
        mock.patch.object(pairing.tap_api, "fetch_all_beers", return_value=[beer]),
        mock.patch.object(pairing.untappd_search, "fetch_beer_page", fetch_mock),
        mock.patch.object(pairing.untappd_search, "search_beer", search_mock),
    ):
        UntappdPairing(args=Args()).run()

    fetch_mock.assert_called_once_with("https://untappd.com/b/x/35642")
    search_mock.assert_not_called()

    saved = json.loads(pairings_path.read_text())
    entry = saved["pairings"]["beerstreet::Maisel, Bayreuth, Bavorsko::Maisels Weisse"]
    assert entry["untappd_url"] == "https://untappd.com/b/x/35642"
    assert entry["untappd_name"] == "Maisel's Weisse Original"
    assert entry["query_used"] == pairing.OVERRIDE_QUERY_MARKER


def test_pairing_records_unmatched_when_override_page_unparseable(tmp_path, monkeypatch):
    pairings_path = tmp_path / "pairings.json"
    overrides_path = tmp_path / "overrides.json"
    monkeypatch.setattr(pairing, "PAIRINGS_PATH", pairings_path)
    monkeypatch.setattr(pairing.overrides_module, "OVERRIDES_PATH", overrides_path)

    beer = _beer("Maisels Weisse", "Maisel")
    overrides_path.write_text(
        json.dumps({"beerstreet::Maisel::Maisels Weisse": "https://untappd.com/b/broken/1"}),
    )

    with (
        mock.patch.object(pairing.tap_api, "fetch_all_beers", return_value=[beer]),
        mock.patch.object(pairing.untappd_search, "fetch_beer_page", return_value=None),
    ):
        UntappdPairing(args=Args()).run()

    saved = json.loads(pairings_path.read_text())
    entry = saved["unmatched"]["beerstreet::Maisel::Maisels Weisse"]
    assert entry["reason"] == pairing.UNMATCHED_OVERRIDE_PARSE_FAILED


def test_pairing_local_mode_skips_network(tmp_path, monkeypatch):
    pairings_path = tmp_path / "pairings.json"
    monkeypatch.setattr(pairing, "PAIRINGS_PATH", pairings_path)

    fetch_mock = mock.Mock()
    search_mock = mock.Mock()

    with (
        mock.patch.object(pairing.tap_api, "fetch_all_beers", fetch_mock),
        mock.patch.object(pairing.untappd_search, "search_beer", search_mock),
    ):
        UntappdPairing(args=Args(local=True)).run()

    fetch_mock.assert_not_called()
    search_mock.assert_not_called()
    assert pairings_path.exists()


def test_pairing_sends_pushover_notification_when_beer_unmatched(tmp_path, monkeypatch, mock_pushover):
    pairings_path = tmp_path / "pairings.json"
    monkeypatch.setattr(pairing, "PAIRINGS_PATH", pairings_path)

    beer = _beer("Mystery Brew", "Unknown")

    with (
        mock.patch.object(pairing.tap_api, "fetch_all_beers", return_value=[beer]),
        mock.patch.object(pairing.untappd_search, "search_beer", return_value=[]),
    ):
        UntappdPairing(args=Args()).run()

    mock_pushover.assert_called_once()
    message = mock_pushover.call_args.args[0]
    assert "Mystery Brew" in message
    assert "Unknown" in message
    assert pairing.UNMATCHED_NO_CANDIDATES in message
    assert "1 pivo" in message


def test_pairing_skips_pushover_when_all_matched(tmp_path, monkeypatch, mock_pushover):
    pairings_path = tmp_path / "pairings.json"
    monkeypatch.setattr(pairing, "PAIRINGS_PATH", pairings_path)

    beer = _beer("Tears of St Laurent (2020)", "Wild Creatures")
    candidates = [_candidate("Tears of St Laurent (2020)", brewery="Wild Creatures")]

    with (
        mock.patch.object(pairing.tap_api, "fetch_all_beers", return_value=[beer]),
        mock.patch.object(pairing.untappd_search, "search_beer", return_value=candidates),
    ):
        UntappdPairing(args=Args()).run()

    mock_pushover.assert_not_called()


def test_pairing_notificationless_logs_instead_of_pushing(tmp_path, monkeypatch, mock_pushover, caplog):
    pairings_path = tmp_path / "pairings.json"
    monkeypatch.setattr(pairing, "PAIRINGS_PATH", pairings_path)

    beer = _beer("Mystery Brew", "Unknown")

    with (
        mock.patch.object(pairing.tap_api, "fetch_all_beers", return_value=[beer]),
        mock.patch.object(pairing.untappd_search, "search_beer", return_value=[]),
        caplog.at_level(logging.INFO, logger="untappd_pairing.pairing"),
    ):
        UntappdPairing(args=Args(notificationless=True)).run()

    mock_pushover.assert_not_called()
    assert any("Mystery Brew" in record.message and "Unknown" in record.message for record in caplog.records)


def test_pairing_uses_degree_plato_to_match_house_lager(tmp_path, monkeypatch, mock_pushover):
    # Reproduces beerstreet::Loutkář::Loutkář case: name == brewery, candidate
    # name does not contain "Loutkář" but contains the degree from API.
    pairings_path = tmp_path / "pairings.json"
    monkeypatch.setattr(pairing, "PAIRINGS_PATH", pairings_path)

    beer = _beer("Loutkář", brewery="Loutkář", degree_plato=12)

    def fake_search(_query):
        # Untappd returns five candidates for the brewery; only one has 12°
        return [
            _candidate("Saturn 12 IPL", brewery="Pivovar Loutkář", url="https://untappd.com/b/x/saturn"),
            _candidate("Světlý ležák 12", brewery="Pivovar Loutkář", url="https://untappd.com/b/x/12"),
            _candidate("Marioneta 10", brewery="Pivovar Loutkář", url="https://untappd.com/b/x/10"),
        ]

    with (
        mock.patch.object(pairing.tap_api, "fetch_all_beers", return_value=[beer]),
        mock.patch.object(pairing.untappd_search, "search_beer", side_effect=fake_search),
    ):
        UntappdPairing(args=Args()).run()

    saved = json.loads(pairings_path.read_text())
    assert "beerstreet::Loutkář::Loutkář" in saved["pairings"]
    assert "beerstreet::Loutkář::Loutkář" not in saved["unmatched"]
    mock_pushover.assert_not_called()


def test_pairing_pushover_failure_does_not_crash_run(tmp_path, monkeypatch, mock_pushover, caplog):
    pairings_path = tmp_path / "pairings.json"
    monkeypatch.setattr(pairing, "PAIRINGS_PATH", pairings_path)

    beer = _beer("Mystery Brew", "Unknown")
    mock_pushover.side_effect = httpx.ConnectError("boom")

    with (
        mock.patch.object(pairing.tap_api, "fetch_all_beers", return_value=[beer]),
        mock.patch.object(pairing.untappd_search, "search_beer", return_value=[]),
        caplog.at_level(logging.ERROR, logger="untappd_pairing.pairing"),
    ):
        UntappdPairing(args=Args()).run()

    assert pairings_path.exists()
    saved = json.loads(pairings_path.read_text())
    assert "beerstreet::Unknown::Mystery Brew" in saved["unmatched"]
    assert any("Pushover" in record.message for record in caplog.records)
