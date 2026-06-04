from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import TYPE_CHECKING

from openrouter import OpenRouter, errors
from openrouter.components import (
    ChatAssistantMessageTypedDict,
    ChatDeveloperMessageTypedDict,
    ChatSystemMessageTypedDict,
    ChatToolMessageTypedDict,
    ChatUserMessageTypedDict,
)

if TYPE_CHECKING:
    from openrouter.components import ChatAssistantMessage

    from untappd_pairing.tap_api import TapBeer
    from untappd_pairing.untappd_search import UntappdCandidate

logger = logging.getLogger(__name__)

# The SDK types chat.send()'s `messages` as a list over this union of message TypedDicts;
# annotate our message list with it so plain dict literals type-check against the overload.
ChatMessage = (
    ChatSystemMessageTypedDict
    | ChatUserMessageTypedDict
    | ChatDeveloperMessageTypedDict
    | ChatToolMessageTypedDict
    | ChatAssistantMessageTypedDict
)

# Ordered by measured quality+availability (see PLAN.md "Empirické ověření"). The first two
# are confirmed 3/3 and fastest; the rest are fallbacks for when the leading models are
# rate-limited. OPENROUTER_MODEL (comma-separated) overrides this list entirely.
DEFAULT_MODELS: tuple[str, ...] = (
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "moonshotai/kimi-k2.6:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "openrouter/free",
    "z-ai/glm-4.5-air:free",
)

REQUEST_TIMEOUT_S = 90.0
# Generous budget: reasoning free models spend tokens "thinking" before the final JSON, so a
# small limit truncates the answer to empty content.
MAX_TOKENS = 1200
# Free models are flaky: upstream returns 429 ("temporarily rate-limited") / 503 ("no healthy
# upstream") sporadically. Retry a few times before moving to the next model.
RETRY_ERRORS = (errors.TooManyRequestsResponseError, errors.ServiceUnavailableResponseError)
# SDK errors (HTTP non-2xx + connection failures) that mean "this model failed" rather than a
# bug in our own code -- caught so we degrade gracefully to the next model.
SDK_ERRORS = (errors.OpenRouterError, errors.NoResponseError)
MAX_RETRIES = 3
RETRY_BACKOFF_S = 4.0

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


def _models() -> tuple[str, ...]:
    override = os.environ.get("OPENROUTER_MODEL")
    if override:
        models = tuple(m.strip() for m in override.split(",") if m.strip())
        if models:
            return models
    return DEFAULT_MODELS


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


def _message_text(message: ChatAssistantMessage) -> str:
    # `content` may be a plain string, a list of content parts, None, or the SDK's UNSET
    # sentinel -- only a non-empty string is useful here. Reasoning models often leave
    # `content` empty and put the answer (with the final JSON at the end) in `reasoning`.
    content = message.content
    if isinstance(content, str) and (stripped := content.strip()):
        return stripped
    reasoning = message.reasoning
    if isinstance(reasoning, str):
        return reasoning.strip()
    return ""


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


def _call_model(client: OpenRouter, model: str, messages: list[ChatMessage]) -> str:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            res = client.chat.send(
                model=model,
                messages=messages,
                temperature=0,
                max_tokens=MAX_TOKENS,
                stream=False,
            )
        except RETRY_ERRORS as exc:
            if attempt >= MAX_RETRIES:
                raise
            wait = RETRY_BACKOFF_S * attempt
            logger.debug("%s -> %s, retry %d/%d in %.0fs", model, type(exc).__name__, attempt, MAX_RETRIES, wait)
            time.sleep(wait)
            continue
        return _message_text(res.choices[0].message)
    msg = "retry loop exited without returning"  # unreachable: last attempt re-raises
    raise AssertionError(msg)


def adjudicate(beer: TapBeer, candidates: list[UntappdCandidate]) -> UntappdCandidate | None:
    if not candidates:
        return None

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        logger.warning("OPENROUTER_API_KEY not set; skipping LLM adjudication for %s::%s", beer.brewery, beer.name)
        return None

    messages: list[ChatMessage] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(beer, candidates)},
    ]

    with OpenRouter(api_key=api_key, timeout_ms=int(REQUEST_TIMEOUT_S * 1000)) as client:
        for model in _models():
            try:
                text = _call_model(client, model, messages)
            except (*SDK_ERRORS, KeyError, IndexError) as exc:
                logger.warning("LLM model %s failed (%s: %s); trying next", model, type(exc).__name__, exc)
                continue
            try:
                index = _parse_index(text, len(candidates))
            except (json.JSONDecodeError, KeyError, ValueError, TypeError, IndexError) as exc:
                logger.warning("LLM model %s gave unparseable reply (%s: %s)", model, type(exc).__name__, exc)
                return None
            if index is None:
                logger.info("LLM (%s) found no match for %s::%s", model, beer.brewery, beer.name)
                return None
            logger.info("LLM (%s) picked candidate %d for %s::%s", model, index, beer.brewery, beer.name)
            return candidates[index]

    logger.warning("All LLM models failed for %s::%s", beer.brewery, beer.name)
    return None
