from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

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

    def should_retry(self, key: str, now: datetime | None = None) -> bool:
        entry = self.unmatched.get(key)
        if entry is None:
            return True
        if entry.get("reason") in TRANSIENT_UNMATCHED_REASONS:
            return True
        last_tried_raw = entry.get("last_tried_at")
        if not isinstance(last_tried_raw, str):
            return True
        try:
            last_tried = datetime.fromisoformat(last_tried_raw)
        except ValueError:
            return True
        return ((now or common.now_utc()) - last_tried) >= RETRY_AFTER

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

    def record_match(
        self,
        beer: TapBeer,
        result: MatchResult,
        query: str,
        now: datetime | None = None,
        description: str | None = None,
    ) -> None:
        key = beer_key(beer.source, beer.brewery, beer.name)
        entry: dict[str, Any] = {
            "untappd_url": result.candidate.url,
            "untappd_name": result.candidate.name,
            "untappd_brewery": result.candidate.brewery,
            "rating": result.candidate.rating,
            "match_score": result.score,
            "matched_at": common.iso_utc(now or common.now_utc()),
            "query_used": query,
        }
        if description:
            entry["description"] = description
        self.pairings[key] = entry
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
