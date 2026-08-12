from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from untappd_pairing.untappd_search import UntappdCandidate
from utils import common

if TYPE_CHECKING:
    from untappd_pairing.matcher import MatchResult
    from untappd_pairing.tap_api import TapBeer

logger = logging.getLogger(__name__)

PAIRINGS_PATH = Path("untappd_pairing/pairings.json")
SCHEMA_VERSION = 1
RETRY_AFTER = timedelta(days=7)
TRANSIENT_UNMATCHED_REASONS = frozenset({"upstream_error"})


def beer_key(source: str, brewery: str, name: str) -> str:
    return f"{source}::{brewery}::{name}"


def _cooldown_elapsed(entry: dict[str, Any], field_name: str, now: datetime | None = None) -> bool:
    # A missing or unparseable timestamp means "never tried", so the caller should go ahead.
    stamp_raw = entry.get(field_name)
    if not isinstance(stamp_raw, str):
        return True
    try:
        stamp = datetime.fromisoformat(stamp_raw)
    except ValueError:
        return True
    return ((now or common.now_utc()) - stamp) >= RETRY_AFTER


@dataclass
class PairingsStore:
    pairings: dict[str, dict[str, Any]] = field(default_factory=dict)
    unmatched: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> PairingsStore:
        data = common.load_json_dict(path)
        return cls(
            pairings=dict(data.get("pairings") or {}),
            unmatched=dict(data.get("unmatched") or {}),
        )

    def is_paired(self, key: str) -> bool:
        return key in self.pairings

    def get_url(self, key: str) -> str:
        return str(self.pairings[key]["untappd_url"])

    def get_description(self, key: str) -> str | None:
        description = self.pairings[key].get("description")
        return str(description) if description else None

    def stored_candidate(self, key: str) -> UntappdCandidate:
        # Every field was written from an UntappdCandidate, so a description needs no HTTP.
        entry = self.pairings[key]
        return UntappdCandidate(
            name=entry.get("untappd_name") or "",
            brewery=entry.get("untappd_brewery") or "",
            url=entry["untappd_url"],
            rating=entry.get("rating"),
        )

    def needs_description(self, key: str, now: datetime | None = None) -> bool:
        entry = self.pairings.get(key)
        if entry is None or entry.get("description"):
            return False
        # Some beers legitimately have nothing describable; retrying every run would burn the
        # free-model quota for nothing, so wait out the same cooldown as an unmatched beer.
        return _cooldown_elapsed(entry, "description_failed_at", now)

    def set_description(self, key: str, description: str | None, now: datetime | None = None) -> None:
        entry = self.pairings[key]
        if description:
            entry["description"] = description
            entry.pop("description_failed_at", None)
            return
        entry.pop("description", None)
        entry["description_failed_at"] = common.iso_utc(now or common.now_utc())

    def clear_description(self, key: str) -> None:
        # Unlike a failed generation this leaves no cooldown marker: a description dropped for
        # being nonsense should be regenerated on the very next run.
        entry = self.pairings[key]
        entry.pop("description", None)
        entry.pop("description_failed_at", None)

    def should_retry(self, key: str, now: datetime | None = None) -> bool:
        entry = self.unmatched.get(key)
        if entry is None:
            return True
        if entry.get("reason") in TRANSIENT_UNMATCHED_REASONS:
            return True
        return _cooldown_elapsed(entry, "last_tried_at", now)

    def select_pending(
        self,
        beers: list[TapBeer],
        overrides: dict[str, str] | None = None,
        now: datetime | None = None,
    ) -> list[TapBeer]:
        overrides = overrides or {}
        pending: list[TapBeer] = []
        for beer in beers:
            key = beer_key(beer.source, beer.brewery, beer.name)
            if key in overrides:
                if self.pairings.get(key, {}).get("untappd_url") != overrides[key]:
                    pending.append(beer)
                continue
            if self.is_paired(key):
                continue
            if not self.should_retry(key, now=now):
                continue
            pending.append(beer)
        return pending

    def record_match(self, beer: TapBeer, result: MatchResult, query: str, now: datetime | None = None) -> None:
        key = beer_key(beer.source, beer.brewery, beer.name)
        # No description here: one pass over all on-tap beers fills those in afterwards.
        self.pairings[key] = {
            "untappd_url": result.candidate.url,
            "untappd_name": result.candidate.name,
            "untappd_brewery": result.candidate.brewery,
            "rating": result.candidate.rating,
            "match_score": result.score,
            "matched_at": common.iso_utc(now or common.now_utc()),
            "query_used": query,
        }
        self.unmatched.pop(key, None)

    def record_unmatched(self, beer: TapBeer, reason: str, now: datetime | None = None) -> None:
        key = beer_key(beer.source, beer.brewery, beer.name)
        previous = self.unmatched.get(key, {})
        attempts = int(previous.get("attempts") or 0) + 1
        self.unmatched[key] = {
            "attempts": attempts,
            "last_tried_at": common.iso_utc(now or common.now_utc()),
            "reason": reason,
        }

    def save(self, path: Path, now: datetime | None = None) -> None:
        payload = {
            "version": SCHEMA_VERSION,
            "generated_at": common.iso_utc(now or common.now_utc()),
            "pairings": dict(sorted(self.pairings.items())),
            "unmatched": dict(sorted(self.unmatched.items())),
        }
        common.atomic_write_json(path, payload)
