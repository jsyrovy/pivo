import functools
import json
import logging
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup, Tag

from utils import common

logger = logging.getLogger(__name__)

UNTAPPD_BASE_URL = "https://untappd.com"
SEARCH_TIMEOUT = 10.0
SEARCH_HITS_PER_PAGE = 5

ALGOLIA_CONFIG_URL = f"{UNTAPPD_BASE_URL}/search?type=beer"
_SEARCH_CONFIG_RE = re.compile(r"window\.UNTAPPD_SEARCH_CONFIG\s*=\s*(\{.*?\});", re.DOTALL)

# Fallback if UNTAPPD_SEARCH_CONFIG can't be extracted from the page. This is a public,
# search-only Algolia key shipped in every page's client-side JS, not a secret.
_FALLBACK_APP_ID = "9WBO4RQ3HO"
_FALLBACK_SEARCH_KEY = "1d347324d67ec472bb7132c66aead485"
_FALLBACK_BEER_INDEX = "beer"


@dataclass(frozen=True, kw_only=True)
class UntappdCandidate:
    name: str
    brewery: str
    url: str
    rating: float | None


@dataclass(frozen=True, kw_only=True)
class AlgoliaConfig:
    app_id: str
    search_key: str
    beer_index: str


def _positive_float_or_none(value: str | float | None) -> float | None:
    if value is None:
        return None
    try:
        rating = float(value)
    except ValueError:
        return None
    return rating if rating > 0 else None


def _extract_rating(caps_el: Tag | None) -> float | None:
    if caps_el is None:
        return None
    raw = caps_el.get("data-rating")
    if not raw:
        return None
    raw_str = raw if isinstance(raw, str) else raw[0]
    return _positive_float_or_none(raw_str)


def _fallback_config() -> AlgoliaConfig:
    return AlgoliaConfig(app_id=_FALLBACK_APP_ID, search_key=_FALLBACK_SEARCH_KEY, beer_index=_FALLBACK_BEER_INDEX)


def _parse_search_config(html: str) -> AlgoliaConfig:
    match = _SEARCH_CONFIG_RE.search(html)
    if match is None:
        raise ValueError("UNTAPPD_SEARCH_CONFIG not found in page")

    data = json.loads(match.group(1))
    return AlgoliaConfig(
        app_id=data["appId"],
        search_key=data["searchKey"],
        beer_index=data["indexes"]["beer"]["all"],
    )


@functools.cache
def _get_search_config() -> AlgoliaConfig:
    try:
        html = common.download_page(ALGOLIA_CONFIG_URL, timeout=SEARCH_TIMEOUT)
        return _parse_search_config(html)
    except httpx.HTTPError, ValueError, KeyError, json.JSONDecodeError:
        logger.warning("Failed to extract Algolia search config from Untappd page, using fallback")
        return _fallback_config()


def _candidate_from_hit(hit: dict[str, Any]) -> UntappdCandidate | None:
    name = hit.get("beer_name")
    brewery = hit.get("brewery_name")
    slug = hit.get("beer_slug")
    object_id = hit.get("objectID")
    if not name or not brewery or not slug or not object_id:
        return None

    return UntappdCandidate(
        name=name,
        brewery=brewery,
        url=f"{UNTAPPD_BASE_URL}/b/{slug}/{object_id}",
        rating=_positive_float_or_none(hit.get("rating_score")),
    )


def _parse_algolia_hits(data: dict[str, Any]) -> list[UntappdCandidate]:
    results: list[UntappdCandidate] = []
    for hit in data.get("hits", []):
        candidate = _candidate_from_hit(hit)
        if candidate is not None:
            results.append(candidate)
    return results


def search_beer(query: str) -> list[UntappdCandidate]:
    # Untappd's /search page is client-rendered against Algolia; this calls that same
    # undocumented, private backend directly instead of scraping the (now empty) HTML.
    config = _get_search_config()
    url = f"https://{config.app_id}-dsn.algolia.net/1/indexes/{config.beer_index}/query"
    headers = {
        "X-Algolia-Application-Id": config.app_id,
        "X-Algolia-API-Key": config.search_key,
    }
    payload = {"params": urlencode({"query": query, "hitsPerPage": SEARCH_HITS_PER_PAGE})}

    common.random_sleep(max_=5)
    logger.debug("Untappd search: %s", query)
    data = common.post_json(url, payload, extra_headers=headers, timeout=SEARCH_TIMEOUT)
    return _parse_algolia_hits(data)


def parse_beer_page(html: str, url: str) -> UntappdCandidate | None:
    soup = BeautifulSoup(html, "html.parser")
    name_el = soup.select_one("div.name h1")
    brewery_el = soup.select_one("div.name p.brewery a")
    if name_el is None or brewery_el is None:
        return None

    return UntappdCandidate(
        name=name_el.get_text(strip=True),
        brewery=brewery_el.get_text(strip=True),
        url=url,
        rating=_extract_rating(soup.select_one("div.caps[data-rating]")),
    )


def fetch_beer_page(url: str) -> UntappdCandidate | None:
    common.random_sleep(max_=5)
    logger.debug("Untappd beer page: %s", url)
    html = common.download_page(url, timeout=SEARCH_TIMEOUT)
    return parse_beer_page(html, url)
