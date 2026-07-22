from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from untappd_pairing import openrouter_client

if TYPE_CHECKING:
    from untappd_pairing.tap_api import TapBeer
    from untappd_pairing.untappd_search import UntappdCandidate

logger = logging.getLogger(__name__)

# Reasoning free models spend many tokens "thinking" before the final text; too small a budget
# truncates the answer mid-sentence, so keep it generous even though the description is short.
MAX_TOKENS = 1200
# Guard against a runaway model that ignores the length instruction; the popover is small.
MAX_CHARS = 320

SYSTEM_PROMPT = (
    "Jsi znalec piva. Na základě zadaných údajů napiš stručný, čtivý popis piva v češtině.\n"
    "Napiš 1 až 2 věty (maximálně zhruba 300 znaků), které vystihnou charakter piva -- styl, "
    "sílu a k jaké příležitosti se hodí. Piš věcně, nevymýšlej si konkrétní chutě ani suroviny, "
    "které nevyplývají ze zadaných údajů.\n"
    "Odpověz POUZE hotovým popisem v češtině -- žádné úvahy, mezikroky, poznámky ani anglický "
    "text, žádné uvozovky, úvodní fráze ani odrážky. Rovnou první větou začni popisovat pivo."
)


def _build_user_prompt(beer: TapBeer, candidate: UntappdCandidate) -> str:
    lines = [
        f"Název: {candidate.name or beer.name}",
        f"Pivovar: {candidate.brewery or beer.brewery}",
        f"Styl: {beer.style or '(neznámý)'}",
        f"Stupňovitost: {f'{beer.degree_plato:g}°' if beer.degree_plato is not None else '(neznámá)'}",
        f"Obsah alkoholu: {f'{beer.abv:g} % ABV' if beer.abv is not None else '(neznámý)'}",
        f"Hodnocení na Untappd: {f'{candidate.rating:.2f} / 5' if candidate.rating is not None else '(neznámé)'}",
    ]
    return "\n".join(lines)


def _clean(text: str) -> str:
    stripped = text.strip().strip('"').strip()
    # Collapse any accidental line breaks -- the popover renders a single flowing paragraph.
    collapsed = re.sub(r"\s+", " ", stripped)
    if len(collapsed) > MAX_CHARS:
        return collapsed[: MAX_CHARS - 1].rstrip() + "…"
    return collapsed


def generate(beer: TapBeer, candidate: UntappdCandidate) -> str | None:
    messages: list[openrouter_client.ChatMessage] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(beer, candidate)},
    ]

    text = openrouter_client.complete(messages, max_tokens=MAX_TOKENS)
    if text is None:
        logger.info("No AI description generated for %s::%s", beer.brewery, beer.name)
        return None

    description = _clean(text)
    if not description:
        logger.info("AI returned empty description for %s::%s", beer.brewery, beer.name)
        return None

    logger.info("Generated AI description for %s::%s", beer.brewery, beer.name)
    return description
