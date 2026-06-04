"""Experimental probe for the OpenRouter LLM pairing adjudicator (see PLAN.md).

Standalone, throwaway tooling -- NOT the production module. It exercises the same official
`openrouter` SDK (`from openrouter import OpenRouter`) that the production adjudicator will
use, so what the probe measures matches what production will run.

Stages (run incrementally via --stage):

  ping    Pure communication test: one trivial request to one model. Proves the API
          key, connectivity and response shape work before touching real data.
  cases   Run the labeled pairing cases (the unmatched-with-candidates fixtures) through
          a single model. Prints per-case PASS/FAIL, latency, parsed index, reasoning.
  models  Run every candidate free model across every case -> accuracy/latency scoreboard.
          This is the "pick the best free model" step.

Usage (run from the repo root):
  uv run --no-dev --env-file .env llm_pairing_probe.py --stage ping
  uv run --no-dev --env-file .env llm_pairing_probe.py --stage cases --model openrouter/free
  uv run --no-dev --env-file .env llm_pairing_probe.py --stage models
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass

from openrouter import OpenRouter, errors
from openrouter.components import (
    ChatAssistantMessage,
    ChatAssistantMessageTypedDict,
    ChatDeveloperMessageTypedDict,
    ChatSystemMessageTypedDict,
    ChatToolMessageTypedDict,
    ChatUserMessageTypedDict,
)

from untappd_pairing.fixtures import FIXTURES_PATH, FixturesStore, expand_url
from untappd_pairing.tap_api import TapBeer
from untappd_pairing.untappd_search import UntappdCandidate
from utils.logging import configure_logging

# The SDK's chat.send() types `messages` as a list over this union of message TypedDicts;
# annotate our message lists with it so plain dict literals type-check against the overload.
ChatMessage = (
    ChatSystemMessageTypedDict
    | ChatUserMessageTypedDict
    | ChatDeveloperMessageTypedDict
    | ChatToolMessageTypedDict
    | ChatAssistantMessageTypedDict
)

logger = logging.getLogger("llm_pairing_probe")

REQUEST_TIMEOUT_S = 90.0
# Generous budget: reasoning free models (glm-4.5-air, nemotron) spend tokens "thinking"
# before the final JSON, so a small limit truncates the answer to empty content.
MAX_TOKENS = 1200
# Free models are flaky: upstream returns 429 ("temporarily rate-limited") / 503
# ("no healthy upstream") sporadically. Retry a few times before giving up.
RETRY_ERRORS = (errors.TooManyRequestsResponseError, errors.ServiceUnavailableResponseError)
# SDK errors (HTTP non-2xx + connection failures) that mean "this model failed" rather than
# a bug in our own code -- caught so the probe degrades gracefully to the next model/case.
SDK_ERRORS = (errors.OpenRouterError, errors.NoResponseError)
MAX_RETRIES = 3
RETRY_BACKOFF_S = 4.0

# All chat-capable free models on OpenRouter as of 2026-06, enumerated from
# GET /api/v1/models filtered to pricing.prompt == pricing.completion == "0" (the plan's
# gemini-2.0-flash-exp is gone). Audio models (google/lyria-3-*) are excluded. Ordering is
# rough quality prior for a structured selection task; the `models` stage measures the rest.
CANDIDATE_MODELS: tuple[str, ...] = (
    # Confirmed 3/3 on the labeled cases when they responded, ordered by measured latency.
    "nvidia/nemotron-3-nano-30b-a3b:free",  # 3/3, ~11s -- best: accurate and fastest
    "moonshotai/kimi-k2.6:free",  # 3/3, ~43s
    "nvidia/nemotron-3-super-120b-a12b:free",  # 3/3, ~66s, 1M context
    "openrouter/free",  # 3/3, ~76s (auto-router over free models)
    "z-ai/glm-4.5-air:free",  # 3/3 then 2/3 (one case rate-limited; reasoning model, slow)
    # Rate-limited (429/503) during probing -- accuracy unmeasured, kept because availability rotates.
    "openai/gpt-oss-120b:free",
    "openai/gpt-oss-20b:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "nvidia/nemotron-nano-9b-v2:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen3-coder:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
)

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


@dataclass(frozen=True, kw_only=True)
class Case:
    key: str
    beer: TapBeer
    candidates: list[UntappdCandidate]
    expected_url: str | None  # compressed url ("/b/..."); None => expect no match


@dataclass(frozen=True, kw_only=True)
class CallResult:
    raw: str
    index: int | None
    reasoning: str
    latency_s: float
    error: str | None = None


# --- prompt + parsing -------------------------------------------------------------------


def build_user_prompt(beer: TapBeer, candidates: list[UntappdCandidate]) -> str:
    lines = [
        "BEER:",
        f"  name: {beer.name}",
        f"  brewery: {beer.brewery}",
        f"  style: {beer.style or '(unknown)'}",
        f"  degree_plato: {beer.degree_plato if beer.degree_plato is not None else '(unknown)'}",
        "",
        "CANDIDATES:",
    ]
    for i, c in enumerate(candidates):
        rating = f"{c.rating:.2f}" if c.rating is not None else "?"
        lines.append(f"  [{i}] name: {c.name!r} | brewery: {c.brewery!r} | rating: {rating}")
    lines.append("")
    lines.append('Return {"index": <int or null>, "reasoning": "<short>"}.')
    return "\n".join(lines)


def parse_index(text: str, num_candidates: int) -> tuple[int | None, str]:
    """Defensively extract {"index": int|null} from a model reply. Returns (index, reasoning)."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE | re.MULTILINE).strip()

    obj: dict[str, object] | None = None
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match:
            try:
                obj = json.loads(match.group(0))
            except json.JSONDecodeError:
                obj = None

    if not isinstance(obj, dict):
        msg = f"no JSON object in reply: {text[:120]!r}"
        raise TypeError(msg)

    reasoning = str(obj.get("reasoning") or "")
    raw_index = obj.get("index")
    if raw_index is None:
        return None, reasoning
    if not isinstance(raw_index, int | float | str):
        msg = f"index has unexpected type {type(raw_index).__name__}"
        raise TypeError(msg)
    idx = int(raw_index)  # may raise ValueError -> caller handles
    if not (0 <= idx < num_candidates):
        msg = f"index {idx} out of range 0..{num_candidates - 1}"
        raise ValueError(msg)
    return idx, reasoning


# --- openrouter call --------------------------------------------------------------------


def message_text(message: ChatAssistantMessage) -> str:
    """Extract usable assistant text from an SDK message.

    `content` may be a plain string, a list of content parts, None, or the SDK's UNSET
    sentinel -- only a non-empty string is useful here. Reasoning models often leave
    `content` empty and put the answer (with the final JSON at the end) in `reasoning`.
    """
    content = message.content
    if isinstance(content, str) and (stripped := content.strip()):
        return stripped
    reasoning = message.reasoning
    if isinstance(reasoning, str):
        return reasoning.strip()
    return ""


def call_model(client: OpenRouter, model: str, messages: list[ChatMessage]) -> tuple[str, float]:
    """Return (assistant_text, latency_seconds). Retries transient 429/503; raises otherwise."""
    start = time.monotonic()
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
        return message_text(res.choices[0].message), time.monotonic() - start
    msg = "retry loop exited without returning"  # unreachable: last attempt re-raises
    raise AssertionError(msg)


def adjudicate(client: OpenRouter, model: str, case: Case) -> CallResult:
    messages: list[ChatMessage] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(case.beer, case.candidates)},
    ]
    try:
        text, latency = call_model(client, model, messages)
    except (*SDK_ERRORS, KeyError, IndexError) as exc:
        return CallResult(raw="", index=None, reasoning="", latency_s=0.0, error=f"{type(exc).__name__}: {exc}")
    try:
        index, reasoning = parse_index(text, len(case.candidates))
    except (ValueError, TypeError) as exc:
        return CallResult(raw=text, index=None, reasoning="", latency_s=latency, error=f"parse: {exc}")
    return CallResult(raw=text, index=index, reasoning=reasoning, latency_s=latency)


# --- cases from fixtures ----------------------------------------------------------------

# Expected URLs for the unmatched-with-candidates fixtures. None => the beer is genuinely
# not on Untappd and the model must return null (Silk Road / BrewDog trap).
EXPECTED: dict[str, str | None] = {
    "ambasada::Maisel & Friends, Bayreuth, Bavorsko::13,7° Artbeer #8": (
        "/b/brauerei-gebr-maisel-maisel-friends-hazy-ipa-artbeer-8-lobster-robin/6590479"
    ),
    "beerstreet::Kynšperský zajíc::Summer Ale": "/b/kynspersky-pivovar-summer-ale/4267619",
    "beerstreet::Záhora::Silk Road": None,
}


def load_cases() -> list[Case]:
    store = FixturesStore.load(FIXTURES_PATH)
    cases: list[Case] = []
    for key, rec in store.records.items():
        if rec.outcome.matched_url is not None or not rec.candidates:
            continue  # only unmatched fixtures that still had candidates
        beer = TapBeer(
            name=rec.beer.name,
            brewery=rec.beer.brewery,
            style=rec.beer.style,
            abv=None,
            degree_plato=rec.beer.degree_plato,
            source=rec.beer.source,
        )
        candidates = [
            UntappdCandidate(name=c.name, brewery=c.brewery, url=expand_url(c.url), rating=c.rating)
            for c in rec.candidates
        ]
        cases.append(Case(key=key, beer=beer, candidates=candidates, expected_url=EXPECTED.get(key, "?UNKNOWN")))
    return cases


def expected_index(case: Case) -> int | None:
    if case.expected_url is None:
        return None
    for i, c in enumerate(case.candidates):
        if c.url.endswith(case.expected_url):
            return i
    return None


# --- stages -----------------------------------------------------------------------------


def stage_ping(client: OpenRouter, models: tuple[str, ...]) -> int:
    messages: list[ChatMessage] = [
        {"role": "user", "content": 'Reply with exactly this JSON and nothing else: {"ok": true}'},
    ]
    for model in models:
        logger.info("PING -> %s", model)
        try:
            text, latency = call_model(client, model, messages)
        except (*SDK_ERRORS, KeyError, IndexError) as exc:
            logger.warning("  unavailable: %s", exc)
            continue
        if not text:
            logger.warning("  empty reply (model answered but produced no content)")
            continue
        logger.info("  OK in %.2fs | reply: %s", latency, text[:200])
        return 0
    logger.error("No candidate model responded (free tier rate-limited?)")
    return 1


def _verdict(case: Case, result: CallResult) -> bool:
    return result.error is None and result.index == expected_index(case)


def stage_cases(client: OpenRouter, model: str) -> int:
    cases = load_cases()
    logger.info("CASES -> %s (%d cases)", model, len(cases))
    passed = 0
    for case in cases:
        exp = expected_index(case)
        result = adjudicate(client, model, case)
        ok = _verdict(case, result)
        passed += ok
        logger.info("%s", "-" * 80)
        logger.info("%s :: %s", case.beer.brewery, case.beer.name)
        logger.info("  expected index=%s (%s)", exp, case.expected_url)
        if result.error:
            logger.info("  ERROR: %s", result.error)
            if result.raw:
                logger.info("  raw: %s", result.raw[:200])
        else:
            reason = result.reasoning[:160]
            logger.info("  got index=%s in %.2fs | reasoning: %s", result.index, result.latency_s, reason)
        logger.info("  => %s", "PASS" if ok else "FAIL")
    logger.info("%s", "=" * 80)
    logger.info("%s: %d/%d passed", model, passed, len(cases))
    return 0 if passed == len(cases) else 1


def stage_models(client: OpenRouter, models: tuple[str, ...]) -> int:
    cases = load_cases()
    logger.info("MODELS scoreboard: %d models x %d cases", len(models), len(cases))
    scoreboard: list[tuple[str, int, float, int]] = []
    for model in models:
        passed = 0
        total_latency = 0.0
        error_count = 0
        for case in cases:
            result = adjudicate(client, model, case)
            if result.error:
                error_count += 1
            total_latency += result.latency_s
            passed += _verdict(case, result)
            logger.debug("%s | %s -> index=%s err=%s", model, case.key, result.index, result.error)
        scoreboard.append((model, passed, total_latency, error_count))
        logger.info("  %-52s %d/%d  (%.1fs total, %d errors)", model, passed, len(cases), total_latency, error_count)
    logger.info("%s", "=" * 80)
    scoreboard.sort(key=lambda r: (-r[1], r[2]))
    logger.info("RANKING (accuracy desc, then latency asc):")
    for model, passed, latency, error_count in scoreboard:
        logger.info("  %d/%d  %6.1fs  %d err  %s", passed, len(cases), latency, error_count, model)
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description="OpenRouter LLM pairing probe")
    parser.add_argument("--stage", choices=("ping", "cases", "models"), default="ping")
    parser.add_argument("--model", default=CANDIDATE_MODELS[0], help="model id for ping/cases stages")
    args = parser.parse_args(argv)

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        logger.error("OPENROUTER_API_KEY not set (run with --env-file .env)")
        return 2

    with OpenRouter(api_key=api_key, timeout_ms=int(REQUEST_TIMEOUT_S * 1000)) as client:
        if args.stage == "ping":
            return stage_ping(client, CANDIDATE_MODELS)
        if args.stage == "cases":
            return stage_cases(client, args.model)
        return stage_models(client, CANDIDATE_MODELS)


if __name__ == "__main__":
    sys.exit(main())
