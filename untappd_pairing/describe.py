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

# The model answers with this single word when the inputs carry no substance to describe;
# an empty popover is better than a sentence of filler.
NO_DESCRIPTION_SENTINEL = "NELZE"

SYSTEM_PROMPT = (
    "Jsi zkušený pivní degustátor. Ze zadaných údajů napiš česky stručný popis toho, JAKÉ TO "
    "PIVO JE -- co od něj čekat v aroma, chuti, hořkosti a plnosti těla.\n"
    "\n"
    "Vycházej VÝHRADNĚ ze zadaných údajů:\n"
    "- ze stylu piva odvoď jeho typický senzorický profil,\n"
    "- ze stupňovitosti a alkoholu odvoď plnost a sílu,\n"
    "- z názvu vycházej jen tehdy, když z něj jednoznačně plyne konkrétní surovina nebo postup "
    "(odrůda chmele, ovoce, koření, sud, druh kvašení, nealko) -- pak popiš, co taková surovina "
    "nebo postup do piva přináší.\n"
    "\n"
    "Je ZAKÁZÁNO:\n"
    "- vymýšlet si chuťové noty, suroviny, historii nebo cokoli, co ze zadaných údajů neplyne,\n"
    "- psát, k jakému jídlu, počasí, příležitosti nebo náladě se pivo hodí,\n"
    "- opakovat název piva, pivovar, stupňovitost, procenta alkoholu ani číslo hodnocení -- "
    "uživatel je vidí hned vedle popisu,\n"
    "- pivo chválit nebo hanit nad rámec pravidla o hodnocení níže.\n"
    "\n"
    "Hodnocení na Untappd zmiň jedním krátkým přívlastkem POUZE tehdy, je-li 3,80 a vyšší "
    "(nadprůměrně hodnocené) nebo nižší než 3,40 (podprůměrně hodnocené). Jinak ho nezmiňuj vůbec.\n"
    "\n"
    "Pokud je styl neznámý a ani z názvu neplyne nic konkrétního, odpověz jediným slovem: "
    f"{NO_DESCRIPTION_SENTINEL}\n"
    "\n"
    "Příklady správné odpovědi:\n"
    "- West coast IPA, 13°, 6,1 %, jalovec v názvu -> Silně chmelená západní IPA s výraznou "
    "hořkostí, citrusovým a pryskyřičným aroma a suchým závěrem. Jalovec přidává bylinný, "
    "lehce jehličnatý tón.\n"
    "- Světlý ležák, 11°, 4,6 %, hodnocení 3,52 -> Klasický světlý ležák: sladový základ, "
    "jemná chmelová hořkost a lehčí tělo, spodně kvašený a čistý v chuti.\n"
    "- Fruity berliner weisse, 11°, jahody v názvu -> Kyselé svrchně kvašené pivo s ostrou "
    "citronovou kyselinkou a lehkým tělem; jahody přidávají sladší ovocný tón, který kyselost "
    "změkčuje.\n"
    "\n"
    "Formát: 1 až 2 věty, maximálně zhruba 300 znaků.\n"
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
    # The tap list and Untappd often name the same beer differently and one of the two may carry
    # the ingredient hint ("Moves - White Grapes and Strawberries"), so offer both when they differ.
    if candidate.name and beer.name and candidate.name != beer.name:
        lines.insert(1, f"Název na výčepu: {beer.name}")
    return "\n".join(lines)


def _clean(text: str) -> str:
    stripped = text.strip().strip('"').strip()
    # Collapse any accidental line breaks -- the popover renders a single flowing paragraph.
    collapsed = re.sub(r"\s+", " ", stripped)
    if len(collapsed) > MAX_CHARS:
        return collapsed[: MAX_CHARS - 1].rstrip() + "…"
    return collapsed


def _is_refusal(description: str) -> bool:
    # Weak models tend to dress the sentinel up ("NELZE." / "Nelze popsat"), so match the prefix.
    return description.upper().startswith(NO_DESCRIPTION_SENTINEL)


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

    if _is_refusal(description):
        logger.info("Not enough facts to describe %s::%s", beer.brewery, beer.name)
        return None

    logger.info("Generated AI description for %s::%s", beer.brewery, beer.name)
    return description
