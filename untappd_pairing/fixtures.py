from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast, get_args

from untappd_pairing import matcher
from untappd_pairing.store import beer_key
from untappd_pairing.untappd_search import UntappdCandidate
from utils import common

if TYPE_CHECKING:
    from datetime import datetime

    from untappd_pairing.tap_api import TapBeer

logger = logging.getLogger(__name__)

FIXTURES_PATH = Path("untappd_pairing/fixtures.json")
SCHEMA_VERSION = 1

Verdict = Literal["wrong_match", "should_match", "not_on_untappd", "expected_missing"]
VALID_VERDICTS: frozenset[str] = frozenset(get_args(Verdict))


def compress_url(url: str) -> str:
    if url.startswith(common.BASE_URL):
        return url[len(common.BASE_URL) :]
    return url


def expand_url(url: str) -> str:
    if url.startswith("/"):
        return f"{common.BASE_URL}{url}"
    return url


@dataclass(frozen=True, kw_only=True)
class FixtureBeer:
    source: str
    brewery: str
    name: str
    style: str
    degree_plato: float | None


@dataclass(frozen=True, kw_only=True)
class FixtureCandidate:
    name: str
    brewery: str
    url: str
    rating: float | None


@dataclass(frozen=True, kw_only=True)
class FixtureAttempt:
    query: str
    hits: tuple[int, ...]


@dataclass(frozen=True, kw_only=True)
class FixtureOutcome:
    matched_url: str | None
    score: float | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if (self.matched_url is None) == (self.reason is None):
            raise ValueError("FixtureOutcome must set exactly one of matched_url or reason")


@dataclass(frozen=True, kw_only=True)
class FixtureAnnotation:
    verdict: Verdict
    expected_url: str | None = None
    note: str = ""


@dataclass
class FixtureRecord:
    beer: FixtureBeer
    candidates: list[FixtureCandidate]
    attempts: list[FixtureAttempt]
    outcome: FixtureOutcome
    captured_at: str
    annotation: FixtureAnnotation | None = None


def _dedup_candidates(
    attempts: list[tuple[str, list[UntappdCandidate]]],
) -> tuple[list[FixtureCandidate], list[FixtureAttempt]]:
    pool: list[FixtureCandidate] = []
    index_by_url: dict[str, int] = {}
    recorded_attempts: list[FixtureAttempt] = []
    for query, candidates in attempts:
        hits: list[int] = []
        for candidate in candidates:
            compressed = compress_url(candidate.url)
            idx = index_by_url.get(compressed)
            if idx is None:
                idx = len(pool)
                index_by_url[compressed] = idx
                pool.append(
                    FixtureCandidate(
                        name=candidate.name,
                        brewery=candidate.brewery,
                        url=compressed,
                        rating=candidate.rating,
                    ),
                )
            hits.append(idx)
        recorded_attempts.append(FixtureAttempt(query=query, hits=tuple(hits)))
    return pool, recorded_attempts


def _parse_beer(raw: dict[str, Any]) -> FixtureBeer:
    plato_raw = raw.get("degree_plato")
    plato = float(plato_raw) if plato_raw is not None else None
    return FixtureBeer(
        source=str(raw["source"]),
        brewery=str(raw["brewery"]),
        name=str(raw["name"]),
        style=str(raw.get("style") or ""),
        degree_plato=plato,
    )


def _parse_candidate(raw: dict[str, Any]) -> FixtureCandidate:
    rating_raw = raw.get("rating")
    rating = float(rating_raw) if rating_raw is not None else None
    return FixtureCandidate(
        name=str(raw["name"]),
        brewery=str(raw["brewery"]),
        url=str(raw["url"]),
        rating=rating,
    )


def _parse_attempt(raw: dict[str, Any]) -> FixtureAttempt:
    hits_raw = raw.get("hits") or []
    return FixtureAttempt(query=str(raw["query"]), hits=tuple(int(i) for i in hits_raw))


def _parse_outcome(raw: dict[str, Any]) -> FixtureOutcome:
    matched = raw.get("matched")
    score_raw = raw.get("score")
    score = float(score_raw) if score_raw is not None else None
    reason = raw.get("reason")
    return FixtureOutcome(
        matched_url=str(matched) if matched is not None else None,
        score=score,
        reason=str(reason) if reason is not None else None,
    )


def _parse_annotation(raw: dict[str, Any]) -> FixtureAnnotation | None:
    verdict = raw.get("verdict")
    if verdict not in VALID_VERDICTS:
        logger.error("Fixture annotation has invalid verdict %r; dropping", verdict)
        return None
    expected = raw.get("expected")
    return FixtureAnnotation(
        verdict=cast("Verdict", verdict),
        expected_url=str(expected) if expected is not None else None,
        note=str(raw.get("note") or ""),
    )


def _parse_record(raw: dict[str, Any]) -> FixtureRecord | None:
    try:
        beer = _parse_beer(raw["beer"])
        candidates = [_parse_candidate(c) for c in raw.get("candidates") or []]
        attempts = [_parse_attempt(a) for a in raw.get("attempts") or []]
        outcome = _parse_outcome(raw["outcome"])
    except KeyError, TypeError, ValueError:
        logger.exception("Failed to parse fixture record; skipping")
        return None
    annotation_raw = raw.get("annotation")
    annotation = _parse_annotation(annotation_raw) if isinstance(annotation_raw, dict) else None
    return FixtureRecord(
        beer=beer,
        candidates=candidates,
        attempts=attempts,
        outcome=outcome,
        captured_at=str(raw.get("captured_at") or ""),
        annotation=annotation,
    )


def _serialize_beer(beer: FixtureBeer) -> dict[str, Any]:
    return {
        "source": beer.source,
        "brewery": beer.brewery,
        "name": beer.name,
        "style": beer.style,
        "degree_plato": beer.degree_plato,
    }


def _serialize_candidate(candidate: FixtureCandidate) -> dict[str, Any]:
    return {
        "name": candidate.name,
        "brewery": candidate.brewery,
        "url": candidate.url,
        "rating": candidate.rating,
    }


def _serialize_attempt(attempt: FixtureAttempt) -> dict[str, Any]:
    return {"query": attempt.query, "hits": list(attempt.hits)}


def _serialize_outcome(outcome: FixtureOutcome) -> dict[str, Any]:
    payload: dict[str, Any] = {"matched": outcome.matched_url}
    if outcome.score is not None:
        payload["score"] = outcome.score
    if outcome.reason is not None:
        payload["reason"] = outcome.reason
    return payload


def _serialize_annotation(annotation: FixtureAnnotation) -> dict[str, Any]:
    return {
        "verdict": annotation.verdict,
        "expected": annotation.expected_url,
        "note": annotation.note,
    }


def _serialize_record(record: FixtureRecord) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "beer": _serialize_beer(record.beer),
        "captured_at": record.captured_at,
        "candidates": [_serialize_candidate(c) for c in record.candidates],
        "attempts": [_serialize_attempt(a) for a in record.attempts],
        "outcome": _serialize_outcome(record.outcome),
    }
    if record.annotation is not None:
        payload["annotation"] = _serialize_annotation(record.annotation)
    return payload


@dataclass
class FixturesStore:
    records: dict[str, FixtureRecord] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> FixturesStore:
        data = common.load_json_dict(path)
        raw_fixtures = data.get("fixtures") or {}
        records: dict[str, FixtureRecord] = {}
        for key, raw in raw_fixtures.items():
            if not isinstance(raw, dict):
                continue
            record = _parse_record(raw)
            if record is not None:
                records[str(key)] = record
        return cls(records=records)

    def upsert(
        self,
        beer: TapBeer,
        attempts: list[tuple[str, list[UntappdCandidate]]],
        outcome: FixtureOutcome,
        now: datetime | None = None,
    ) -> None:
        key = beer_key(beer.source, beer.brewery, beer.name)
        candidates, recorded_attempts = _dedup_candidates(attempts)
        previous = self.records.get(key)
        annotation = previous.annotation if previous is not None else None
        self.records[key] = FixtureRecord(
            beer=FixtureBeer(
                source=beer.source,
                brewery=beer.brewery,
                name=beer.name,
                style=beer.style,
                degree_plato=beer.degree_plato,
            ),
            candidates=candidates,
            attempts=recorded_attempts,
            outcome=outcome,
            captured_at=common.iso_utc(now or common.now_utc()),
            annotation=annotation,
        )

    def save(self, path: Path, now: datetime | None = None) -> None:
        payload = {
            "version": SCHEMA_VERSION,
            "generated_at": common.iso_utc(now or common.now_utc()),
            "fixtures": {key: _serialize_record(self.records[key]) for key in sorted(self.records)},
        }
        common.atomic_write_json(path, payload)


def _candidates_for_attempt(record: FixtureRecord, hits: tuple[int, ...]) -> list[UntappdCandidate]:
    return [
        UntappdCandidate(
            name=record.candidates[i].name,
            brewery=record.candidates[i].brewery,
            url=expand_url(record.candidates[i].url),
            rating=record.candidates[i].rating,
        )
        for i in hits
    ]


def replay(record: FixtureRecord) -> str | None:
    for attempt in record.attempts:
        candidates = _candidates_for_attempt(record, attempt.hits)
        result = matcher.best_match(
            record.beer.name,
            record.beer.brewery,
            candidates,
            record.beer.degree_plato,
            record.beer.style,
        )
        if result is not None:
            return compress_url(result.candidate.url)
    return None


@dataclass(frozen=True, kw_only=True)
class ExpectedOutcome:
    matched_url: str | None
    reason: str


def expected_outcome(record: FixtureRecord) -> ExpectedOutcome | None:
    annotation = record.annotation
    if annotation is None:
        return ExpectedOutcome(matched_url=record.outcome.matched_url, reason="recorded outcome")
    if annotation.verdict in {"wrong_match", "should_match"}:
        return ExpectedOutcome(
            matched_url=annotation.expected_url,
            reason=f"annotation expects {annotation.expected_url}",
        )
    if annotation.verdict == "not_on_untappd":
        return ExpectedOutcome(matched_url=None, reason="annotation expects no match")
    return None
