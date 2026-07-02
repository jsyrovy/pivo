import json
from pathlib import Path
from unittest import mock

import httpx
import pytest
from bs4 import BeautifulSoup

from untappd_pairing import untappd_search

FIXTURES = Path(__file__).parent / "fixtures"


def _read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _reset_search_config_cache():
    untappd_search._get_search_config.cache_clear()
    yield
    untappd_search._get_search_config.cache_clear()


def _search_config_html(app_id="APPID1", search_key="KEY1", index="beer"):
    config = {"appId": app_id, "searchKey": search_key, "indexes": {"beer": {"all": index}}}
    return f"<script>window.UNTAPPD_SEARCH_CONFIG = {json.dumps(config)};</script>"


def test_get_search_config_extracts_from_page():
    with mock.patch.object(untappd_search.common, "download_page", return_value=_search_config_html()):
        config = untappd_search._get_search_config()

    assert config == untappd_search.AlgoliaConfig(app_id="APPID1", search_key="KEY1", beer_index="beer")


def test_get_search_config_caches_across_calls():
    with mock.patch.object(untappd_search.common, "download_page", return_value=_search_config_html()) as mock_dl:
        untappd_search._get_search_config()
        untappd_search._get_search_config()

    mock_dl.assert_called_once()


def test_get_search_config_falls_back_when_config_missing(caplog):
    with mock.patch.object(untappd_search.common, "download_page", return_value="<html></html>"):
        config = untappd_search._get_search_config()

    assert config == untappd_search._fallback_config()
    assert "fallback" in caplog.text.lower()


def test_get_search_config_falls_back_on_download_error(caplog):
    with mock.patch.object(untappd_search.common, "download_page", side_effect=httpx.ConnectError("boom")):
        config = untappd_search._get_search_config()

    assert config == untappd_search._fallback_config()
    assert "fallback" in caplog.text.lower()


def test_search_beer_posts_to_algolia_and_parses_hits():
    hits_payload = json.loads(_read_fixture("algolia_search_response.json"))
    config = untappd_search.AlgoliaConfig(app_id="APPID1", search_key="KEY1", beer_index="beer")

    with (
        mock.patch.object(untappd_search, "_get_search_config", return_value=config),
        mock.patch.object(untappd_search.common, "post_json", return_value=hits_payload) as mock_post,
        mock.patch.object(untappd_search.common, "random_sleep"),
    ):
        candidates = untappd_search.search_beer("Lazy Charboney Fracek")

    called_url = mock_post.call_args.args[0]
    assert called_url == "https://APPID1-dsn.algolia.net/1/indexes/beer/query"
    headers = mock_post.call_args.kwargs["extra_headers"]
    assert headers == {"X-Algolia-Application-Id": "APPID1", "X-Algolia-API-Key": "KEY1"}
    payload = mock_post.call_args.args[1]
    assert "query=Lazy" in payload["params"]

    assert len(candidates) == 1
    assert candidates[0].name == "Lazy Charbonnay"
    assert candidates[0].brewery == "FRACEK"
    assert candidates[0].url == "https://untappd.com/b/fracek-lazy-charbonnay/6648307"
    assert candidates[0].rating == 3.67


def test_parse_algolia_hits_skips_hit_missing_required_fields():
    data = {"hits": [{"beer_name": "Foo"}]}
    assert untappd_search._parse_algolia_hits(data) == []


@pytest.mark.parametrize("rating_score", [None, 0, "not-a-number"])
def test_parse_algolia_hits_treats_non_positive_or_unparseable_rating_as_none(rating_score):
    hit = {"beer_name": "Foo", "brewery_name": "Bar", "beer_slug": "bar-foo", "objectID": "1"}
    if rating_score is not None:
        hit["rating_score"] = rating_score

    candidates = untappd_search._parse_algolia_hits({"hits": [hit]})
    assert candidates[0].rating is None


def test_extract_rating_accepts_data_rating_list():
    soup = BeautifulSoup('<div class="caps" data-rating="3.5"></div>', "html.parser")
    el = soup.select_one("div.caps")
    assert el is not None
    el["data-rating"] = ["4.25", "ignored"]
    assert untappd_search._extract_rating(el) == 4.25


def test_extract_rating_returns_none_for_none_input():
    assert untappd_search._extract_rating(None) is None


def test_extract_rating_returns_none_when_data_rating_attribute_empty():
    soup = BeautifulSoup('<div class="caps" data-rating=""></div>', "html.parser")
    el = soup.select_one("div.caps")
    assert untappd_search._extract_rating(el) is None


def test_fetch_beer_page_calls_download_and_parses():
    html = _read_fixture("untappd_beer_page.html")
    with (
        mock.patch.object(untappd_search.common, "download_page", return_value=html) as mock_download,
        mock.patch.object(untappd_search.common, "random_sleep"),
    ):
        candidate = untappd_search.fetch_beer_page("https://untappd.com/b/x/35642")

    mock_download.assert_called_once()
    assert mock_download.call_args.args[0] == "https://untappd.com/b/x/35642"
    assert candidate is not None
    assert candidate.url == "https://untappd.com/b/x/35642"
    assert candidate.name == "Maisel's Weisse Original"


def test_parse_beer_page_extracts_name_brewery_and_rating():
    html = _read_fixture("untappd_beer_page.html")
    candidate = untappd_search.parse_beer_page(html, "https://untappd.com/b/x/35642")

    assert candidate is not None
    assert candidate.name == "Maisel's Weisse Original"
    assert candidate.brewery == "Brauerei Gebr. Maisel"
    assert candidate.rating == 3.59774
    assert candidate.url == "https://untappd.com/b/x/35642"


def test_parse_beer_page_returns_none_when_required_fields_missing():
    assert untappd_search.parse_beer_page("<html><body></body></html>", "https://x") is None
