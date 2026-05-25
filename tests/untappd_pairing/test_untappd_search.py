from pathlib import Path
from unittest import mock

from bs4 import BeautifulSoup

from untappd_pairing import untappd_search

FIXTURES = Path(__file__).parent / "fixtures"


def _read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_search_results_extracts_candidates():
    html = _read_fixture("untappd_search_tears.html")
    candidates = untappd_search.parse_search_results(html)

    assert candidates, "expected at least one candidate"
    first = candidates[0]
    assert first.name == "Tears of St Laurent (2020)"
    assert first.brewery == "Wild Creatures"
    assert first.url == "https://untappd.com/b/wild-creatures-tears-of-st-laurent-2020/5776418"
    assert first.rating == 4.02


def test_parse_search_results_empty_page():
    html = _read_fixture("untappd_search_empty.html")
    assert untappd_search.parse_search_results(html) == []


def test_parse_handles_missing_rating():
    html = """
    <div class="results-container">
      <div class="beer-item">
        <div class="beer-details">
          <p class="name"><a href="/b/foo/1">Foo Beer</a></p>
          <p class="brewery"><a href="/Foo">Foo Brewery</a></p>
        </div>
      </div>
    </div>
    """
    candidates = untappd_search.parse_search_results(html)
    assert len(candidates) == 1
    assert candidates[0].rating is None


def test_parse_handles_zero_rating_as_none():
    html = """
    <div class="results-container">
      <div class="beer-item">
        <div class="beer-details">
          <p class="name"><a href="/b/foo/1">Foo</a></p>
          <p class="brewery"><a href="/Foo">Foo</a></p>
        </div>
        <div class="rating"><div class="caps" data-rating="0.000"></div></div>
      </div>
    </div>
    """
    candidates = untappd_search.parse_search_results(html)
    assert candidates[0].rating is None


def test_parse_handles_unparseable_rating_as_none():
    html = """
    <div class="results-container">
      <div class="beer-item">
        <div class="beer-details">
          <p class="name"><a href="/b/foo/1">Foo</a></p>
          <p class="brewery"><a href="/Foo">Foo</a></p>
        </div>
        <div class="rating"><div class="caps" data-rating="not-a-number"></div></div>
      </div>
    </div>
    """
    candidates = untappd_search.parse_search_results(html)
    assert candidates[0].rating is None


def test_parse_skips_item_missing_name_or_brewery_link():
    html = """
    <div class="results-container">
      <div class="beer-item">
        <div class="beer-details">
          <p class="brewery"><a href="/OnlyBrewery">Only Brewery</a></p>
        </div>
      </div>
    </div>
    """
    assert untappd_search.parse_search_results(html) == []


def test_parse_skips_item_when_href_is_not_string():
    soup = BeautifulSoup(
        """
        <div class="beer-item">
          <div class="beer-details">
            <p class="name"><a href="/b/foo/1">Foo</a></p>
            <p class="brewery"><a href="/Foo">Foo</a></p>
          </div>
        </div>
        """,
        "html.parser",
    )
    beer_item = soup.select_one("div.beer-item")
    assert beer_item is not None
    name_link = beer_item.select_one("p.name a[href^='/b/']")
    assert name_link is not None
    name_link["href"] = ["/b/foo/1", "/b/foo/2"]
    assert untappd_search._parse_beer_item(beer_item) is None


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


def test_search_beer_calls_download_page_with_search_url():
    html = _read_fixture("untappd_search_empty.html")
    with (
        mock.patch.object(untappd_search.common, "download_page", return_value=html) as mock_download,
        mock.patch.object(untappd_search.common, "random_sleep"),
    ):
        untappd_search.search_beer("Tears of St Laurent (2020) Wild Creatures")

    called_url = mock_download.call_args.args[0]
    assert called_url.startswith("https://untappd.com/search?")
    assert "type=beer" in called_url
    assert "Tears" in called_url
