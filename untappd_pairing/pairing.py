from __future__ import annotations

import logging
from html import escape as html_escape
from typing import TYPE_CHECKING

import httpx

from robot.base import BaseRobot
from untappd_pairing import llm_matcher, matcher, normalize, tap_api, untappd_search
from untappd_pairing import overrides as overrides_module
from untappd_pairing.fixtures import FIXTURES_PATH, FixtureOutcome, FixturesStore, compress_url
from untappd_pairing.matcher import MatchResult
from untappd_pairing.store import PAIRINGS_PATH, PairingsStore, beer_key
from utils import pushover

if TYPE_CHECKING:
    from untappd_pairing.untappd_search import UntappdCandidate

logger = logging.getLogger(__name__)

UNMATCHED_NO_CANDIDATES = "no_candidates_above_threshold"
UNMATCHED_UPSTREAM_ERROR = "upstream_error"
UNMATCHED_OVERRIDE_PARSE_FAILED = "override_page_parse_failed"
OVERRIDE_QUERY_MARKER = "<override>"
LLM_QUERY_MARKER = "<llm>"


def _unique_candidates(trace: list[tuple[str, list[UntappdCandidate]]]) -> list[UntappdCandidate]:
    pool: list[UntappdCandidate] = []
    seen: dict[str, int] = {}
    for _query, candidates in trace:
        for candidate in candidates:
            if candidate.url not in seen:
                seen[candidate.url] = len(pool)
                pool.append(candidate)
    return pool


def _pluralize_pivo(count: int) -> str:
    if count == 1:
        return "pivo"
    if count in {2, 3, 4}:
        return "piva"
    return "piv"


class UntappdPairing(BaseRobot):
    def _main(self) -> None:
        store = PairingsStore.load(PAIRINGS_PATH)
        fixtures_store = FixturesStore.load(FIXTURES_PATH)
        overrides = overrides_module.load(overrides_module.OVERRIDES_PATH)

        if self._args.local:
            logger.info("Local mode: skipping tap-api fetch and Untappd scraping")
            store.save(PAIRINGS_PATH)
            fixtures_store.save(FIXTURES_PATH)
            return

        beers = tap_api.fetch_all_beers()
        logger.info("Fetched %d beers from tap-api", len(beers))

        pending = store.select_pending(beers, overrides=overrides)
        logger.info("Pairing %d pending beers (rest already paired or in cooldown)", len(pending))

        matched: list[tuple[tap_api.TapBeer, str]] = []
        unmatched: list[tuple[tap_api.TapBeer, str]] = []
        for beer in pending:
            reason = self._pair_one(beer, store, fixtures_store, overrides)
            key = beer_key(beer.source, beer.brewery, beer.name)
            if reason is None:
                matched.append((beer, store.get_url(key)))
            else:
                unmatched.append((beer, reason))

        store.save(PAIRINGS_PATH)
        fixtures_store.save(FIXTURES_PATH)
        logger.info(
            "Saved %s (pairings=%d, unmatched=%d, fixtures=%d)",
            PAIRINGS_PATH,
            len(store.pairings),
            len(store.unmatched),
            len(fixtures_store.records),
        )

        if matched or unmatched:
            self._notify_run(matched, unmatched)

    def _notify_run(
        self,
        matched: list[tuple[tap_api.TapBeer, str]],
        unmatched: list[tuple[tap_api.TapBeer, str]],
    ) -> None:
        sections: list[str] = []
        if matched:
            header = f"<b>Naparováno {len(matched)} {_pluralize_pivo(len(matched))}:</b>"
            lines = [
                f"• {html_escape(beer.venue_short)} :: {html_escape(beer.brewery)} :: {html_escape(beer.name)}\n"
                f'  <a href="{html_escape(url, quote=True)}">{html_escape(url)}</a>'
                for beer, url in matched
            ]
            sections.append(header + "\n" + "\n".join(lines))
        if unmatched:
            header = f"<b>Nepodařilo se naparovat {len(unmatched)} {_pluralize_pivo(len(unmatched))}:</b>"
            lines = [
                f"• {html_escape(beer.venue_short)} :: {html_escape(beer.brewery)}"
                f" :: {html_escape(beer.name)} <i>({html_escape(reason)})</i>"
                for beer, reason in unmatched
            ]
            sections.append(header + "\n" + "\n".join(lines))
        message = "\n\n".join(sections)

        if self._args.notificationless:
            logger.info(message)
            return

        try:
            pushover.send_notification(message, html=True)
        except httpx.HTTPError:
            logger.exception("Failed to send Pushover notification about pairing run")

    @staticmethod
    def _pair_one(
        beer: tap_api.TapBeer,
        store: PairingsStore,
        fixtures_store: FixturesStore,
        overrides: dict[str, str],
    ) -> str | None:
        key = beer_key(beer.source, beer.brewery, beer.name)
        if key in overrides:
            return UntappdPairing._pair_via_override(beer, store, overrides[key])

        return UntappdPairing._pair_via_search(beer, store, fixtures_store)

    @staticmethod
    def _pair_via_override(beer: tap_api.TapBeer, store: PairingsStore, url: str) -> str | None:
        try:
            candidate = untappd_search.fetch_beer_page(url)
        except httpx.HTTPError:
            logger.exception("Failed to fetch override URL %s", url)
            store.record_unmatched(beer, UNMATCHED_UPSTREAM_ERROR)
            return UNMATCHED_UPSTREAM_ERROR

        if candidate is None:
            logger.error("Could not parse override beer page %s", url)
            store.record_unmatched(beer, UNMATCHED_OVERRIDE_PARSE_FAILED)
            return UNMATCHED_OVERRIDE_PARSE_FAILED

        result = MatchResult(candidate=candidate, score=1.0, brewery_matched=True)
        logger.info("Override matched %s::%s -> %s", beer.brewery, beer.name, url)
        store.record_match(beer, result, OVERRIDE_QUERY_MARKER)
        return None

    @staticmethod
    def _pair_via_search(beer: tap_api.TapBeer, store: PairingsStore, fixtures_store: FixturesStore) -> str | None:
        queries = normalize.build_search_queries(beer.name, beer.brewery, beer.degree_plato)
        trace: list[tuple[str, list[UntappdCandidate]]] = []

        for query in queries:
            try:
                candidates = untappd_search.search_beer(query)
            except httpx.HTTPError:
                logger.exception("Untappd search failed for '%s'", query)
                store.record_unmatched(beer, UNMATCHED_UPSTREAM_ERROR)
                return UNMATCHED_UPSTREAM_ERROR

            trace.append((query, candidates))

            result = matcher.best_match(beer.name, beer.brewery, candidates, beer.degree_plato, beer.style)
            if result is not None:
                logger.info(
                    "Matched %s::%s -> %s (score=%.2f)",
                    beer.brewery,
                    beer.name,
                    result.candidate.url,
                    result.score,
                )
                store.record_match(beer, result, query)
                fixtures_store.upsert(
                    beer,
                    trace,
                    FixtureOutcome(matched_url=compress_url(result.candidate.url), score=result.score),
                )
                return None

        pool = _unique_candidates(trace)
        if pool:
            chosen = llm_matcher.adjudicate(beer, pool)
            if chosen is not None:
                result = MatchResult(
                    candidate=chosen,
                    score=matcher.name_overlap(beer.name, chosen.name),
                    brewery_matched=matcher.brewery_matches(beer.brewery, chosen.brewery),
                )
                logger.info("LLM matched %s::%s -> %s", beer.brewery, beer.name, chosen.url)
                store.record_match(beer, result, LLM_QUERY_MARKER)
                fixtures_store.upsert(
                    beer,
                    trace,
                    FixtureOutcome(matched_url=compress_url(chosen.url), source="llm"),
                )
                return None

        logger.info("No match for %s::%s after %d queries", beer.brewery, beer.name, len(queries))
        store.record_unmatched(beer, UNMATCHED_NO_CANDIDATES)
        fixtures_store.upsert(
            beer,
            trace,
            FixtureOutcome(matched_url=None, reason=UNMATCHED_NO_CANDIDATES),
        )
        return UNMATCHED_NO_CANDIDATES
