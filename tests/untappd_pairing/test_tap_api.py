import json
from unittest import mock

from untappd_pairing import tap_api

SAMPLE_PAYLOAD = json.dumps(
    {
        "source": "beerstreet",
        "fetchedAt": "2026-04-17T10:31:13.809Z",
        "beers": [
            {
                "name": "Velikonoční",
                "brewery": "Loutkář",
                "style": "Ležák světlý",
                "abv": 5.3,
                "degreePlato": 12.5,
                "source": "beerstreet",
                "order": 1,
                "pricing": None,
            },
            {
                "name": "Kazbek",
                "brewery": "Klenot",
                "style": "Ležák světlý",
                "abv": None,
                "degreePlato": 11,
                "source": "beerstreet",
                "order": 2,
                "pricing": None,
            },
        ],
    },
)


def test_fetch_endpoint_sets_origin_header_and_returns_typed_beers():
    with mock.patch.object(tap_api.common, "download_page", return_value=SAMPLE_PAYLOAD) as mock_download:
        beers = tap_api.fetch_endpoint("/beerstreet")

    args, kwargs = mock_download.call_args
    assert args[0] == "https://tap-api.jiri-syrovy.workers.dev/beerstreet"
    assert kwargs["extra_headers"] == {"Origin": "https://pivo.jsyrovy.cz"}

    assert len(beers) == 2
    assert beers[0] == tap_api.TapBeer(
        name="Velikonoční",
        brewery="Loutkář",
        style="Ležák světlý",
        abv=5.3,
        degree_plato=12.5,
        source="beerstreet",
    )
    assert beers[1].abv is None
    assert beers[1].degree_plato == 11


def test_fetch_endpoint_parses_missing_degree_plato_as_none():
    payload = json.dumps(
        {
            "source": "beerstreet",
            "fetchedAt": "2026-04-17T10:31:13.809Z",
            "beers": [{"name": "Foo", "brewery": "Bar", "style": "IPA", "abv": 5.0, "source": "beerstreet"}],
        },
    )
    with mock.patch.object(tap_api.common, "download_page", return_value=payload):
        beers = tap_api.fetch_endpoint("/beerstreet")

    assert beers[0].degree_plato is None


def test_fetch_all_beers_combines_endpoints():
    payloads = {
        "https://tap-api.jiri-syrovy.workers.dev/beerstreet": SAMPLE_PAYLOAD,
        "https://tap-api.jiri-syrovy.workers.dev/ambasada": json.dumps(
            {"source": "ambasada", "fetchedAt": "x", "beers": []},
        ),
    }

    def fake_download(url, extra_headers=None, timeout=None):  # noqa: ARG001
        return payloads[url]

    with mock.patch.object(tap_api.common, "download_page", side_effect=fake_download):
        beers = tap_api.fetch_all_beers()

    assert [b.source for b in beers] == ["beerstreet", "beerstreet"]


def test_fetch_all_beers_swallows_endpoint_errors(caplog):
    def fake_download(url, extra_headers=None, timeout=None):  # noqa: ARG001
        if "ambasada" in url:
            raise RuntimeError("boom")
        return SAMPLE_PAYLOAD

    with (
        mock.patch.object(tap_api.common, "download_page", side_effect=fake_download),
        caplog.at_level("ERROR"),
    ):
        beers = tap_api.fetch_all_beers()

    assert len(beers) == 2
    assert any("Failed to fetch tap-api endpoint /ambasada" in record.message for record in caplog.records)
