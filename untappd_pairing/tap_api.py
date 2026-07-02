import json
import logging
from dataclasses import dataclass
from typing import Any

from utils import common

logger = logging.getLogger(__name__)

TAP_API_BASE_URL = "https://tap-api.jiri-syrovy.workers.dev"
ALLOWED_ORIGIN = common.DASHBOARD_BASE_URL
ENDPOINTS: tuple[str, ...] = ("/beerstreet", "/ambasada")

VENUE_SHORT: dict[str, str] = {
    "beerstreet": "BS",
    "ambasada": "PA",
}
EMPTY_TAP_PLACEHOLDER = "-"


@dataclass(frozen=True, kw_only=True)
class TapBeer:
    name: str
    brewery: str
    style: str
    abv: float | None
    degree_plato: float | None
    source: str

    @property
    def venue_short(self) -> str:
        return VENUE_SHORT.get(self.source, self.source)


def _parse_beer(raw: dict[str, Any]) -> TapBeer:
    return TapBeer(
        name=str(raw["name"]).strip(),
        brewery=str(raw.get("brewery") or "").strip(),
        style=str(raw.get("style") or "").strip(),
        abv=float(raw["abv"]) if raw.get("abv") is not None else None,
        degree_plato=float(raw["degreePlato"]) if raw.get("degreePlato") is not None else None,
        source=str(raw["source"]),
    )


def _is_empty_tap(beer: TapBeer) -> bool:
    return beer.name == EMPTY_TAP_PLACEHOLDER and beer.brewery == EMPTY_TAP_PLACEHOLDER


def fetch_endpoint(endpoint: str) -> list[TapBeer]:
    url = f"{TAP_API_BASE_URL}{endpoint}"
    body = common.download_page(url, extra_headers={"Origin": ALLOWED_ORIGIN})
    payload = json.loads(body)
    beers = [_parse_beer(beer) for beer in payload.get("beers", [])]
    return [beer for beer in beers if not _is_empty_tap(beer)]


def fetch_all_beers() -> list[TapBeer]:
    beers: list[TapBeer] = []
    for endpoint in ENDPOINTS:
        try:
            beers.extend(fetch_endpoint(endpoint))
        except Exception:
            logger.exception("Failed to fetch tap-api endpoint %s", endpoint)
    return beers
