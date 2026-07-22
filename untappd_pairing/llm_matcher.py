from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

from untappd_pairing import openrouter_client

if TYPE_CHECKING:
    from untappd_pairing.tap_api import TapBeer
    from untappd_pairing.untappd_search import UntappdCandidate

logger = logging.getLogger(__name__)

# Generous budget: reasoning free models spend tokens "thinking" before the final JSON, so a
# small limit truncates the answer to empty content.
MAX_TOKENS = 1200

SYSTEM_PROMPT = (
    "You match a draft beer from a Czech pub tap list to the correct entry on Untappd.\n"
    "You are given the beer and a numbered list of candidate Untappd entries.\n"
    "Pick the candidate that is the SAME beer from the SAME brewery.\n"
    "The brewery name may differ by translation or branding variant -- e.g. "
    '"Maisel & Friends" is the same brewer as "Brauerei Gebr. Maisel", and '
    '"Kynspersky zajic" is the same brewer as "Kynspersky pivovar" -- but it must '
    "provably be the same brewer, not merely a beer with the same name from an unrelated "
    'brewery (e.g. a "Silk Road" from BrewDog is NOT a match for a Czech "Silk Road").\n'
    "If no candidate is the same beer from the same brewery, return null.\n"
    'Respond with ONLY a JSON object: {"index": <int or null>, "reasoning": "<short>"}.'
)


def _build_user_prompt(beer: TapBeer, candidates: list[UntappdCandidate]) -> str:
    lines = [
        "BEER:",
        f"  name: {beer.name}",
        f"  brewery: {beer.brewery}",
        f"  style: {beer.style or '(unknown)'}",
        f"  degree_plato: {beer.degree_plato if beer.degree_plato is not None else '(unknown)'}",
        "",
        "CANDIDATES:",
    ]
    lines.extend(
        f"  [{i}] name: {c.name!r} | brewery: {c.brewery!r} | "
        f"rating: {f'{c.rating:.2f}' if c.rating is not None else '?'}"
        for i, c in enumerate(candidates)
    )
    lines.append("")
    lines.append('Return {"index": <int or null>, "reasoning": "<short>"}.')
    return "\n".join(lines)


def _parse_index(text: str, num_candidates: int) -> int | None:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE | re.MULTILINE).strip()

    obj: object
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError:
        # Reasoning models bury the final JSON at the end of their output: grab the last {...} block.
        matches = re.findall(r"\{.*?\}", cleaned, flags=re.DOTALL)
        obj = json.loads(matches[-1]) if matches else None

    if not isinstance(obj, dict):
        msg = f"no JSON object in reply: {text[:120]!r}"
        raise TypeError(msg)

    raw_index = obj.get("index")
    if raw_index is None:
        return None
    if not isinstance(raw_index, int | float | str):
        msg = f"index has unexpected type {type(raw_index).__name__}"
        raise TypeError(msg)
    idx = int(raw_index)
    if not (0 <= idx < num_candidates):
        msg = f"index {idx} out of range 0..{num_candidates - 1}"
        raise ValueError(msg)
    return idx


def adjudicate(beer: TapBeer, candidates: list[UntappdCandidate]) -> UntappdCandidate | None:
    if not candidates:
        return None

    messages: list[openrouter_client.ChatMessage] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(beer, candidates)},
    ]

    text = openrouter_client.complete(messages, max_tokens=MAX_TOKENS)
    if text is None:
        logger.warning("LLM adjudication unavailable for %s::%s", beer.brewery, beer.name)
        return None

    try:
        index = _parse_index(text, len(candidates))
    except (json.JSONDecodeError, KeyError, ValueError, TypeError, IndexError) as exc:
        logger.warning("LLM gave unparseable reply (%s: %s)", type(exc).__name__, exc)
        return None

    if index is None:
        logger.info("LLM found no match for %s::%s", beer.brewery, beer.name)
        return None

    logger.info("LLM picked candidate %d for %s::%s", index, beer.brewery, beer.name)
    return candidates[index]
