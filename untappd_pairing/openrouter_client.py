from __future__ import annotations

import logging
import os
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
# Free models are flaky: upstream returns 429 ("temporarily rate-limited") / 503 ("no healthy
# upstream") sporadically. Retry a few times before moving to the next model.
RETRY_ERRORS = (errors.TooManyRequestsResponseError, errors.ServiceUnavailableResponseError)
# SDK errors (HTTP non-2xx + connection failures) that mean "this model failed" rather than a
# bug in our own code -- caught so we degrade gracefully to the next model.
SDK_ERRORS = (errors.OpenRouterError, errors.NoResponseError)
MAX_RETRIES = 3
RETRY_BACKOFF_S = 4.0


def models() -> tuple[str, ...]:
    override = os.environ.get("OPENROUTER_MODEL")
    if override:
        chosen = tuple(m.strip() for m in override.split(",") if m.strip())
        if chosen:
            return chosen
    return DEFAULT_MODELS


def message_text(message: ChatAssistantMessage) -> str:
    # `content` may be a plain string, a list of content parts, None, or the SDK's UNSET
    # sentinel -- only a non-empty string is useful here. Reasoning models often leave
    # `content` empty and put the answer in `reasoning`.
    content = message.content
    if isinstance(content, str) and (stripped := content.strip()):
        return stripped
    reasoning = message.reasoning
    if isinstance(reasoning, str):
        return reasoning.strip()
    return ""


def _call_model(client: OpenRouter, model: str, messages: list[ChatMessage], *, max_tokens: int) -> str:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            res = client.chat.send(
                model=model,
                messages=messages,
                temperature=0,
                max_tokens=max_tokens,
                stream=False,
            )
        except RETRY_ERRORS as exc:
            if attempt >= MAX_RETRIES:
                raise
            wait = RETRY_BACKOFF_S * attempt
            logger.debug("%s -> %s, retry %d/%d in %.0fs", model, type(exc).__name__, attempt, MAX_RETRIES, wait)
            time.sleep(wait)
            continue
        return message_text(res.choices[0].message)
    msg = "retry loop exited without returning"  # unreachable: last attempt re-raises
    raise AssertionError(msg)


def complete(messages: list[ChatMessage], *, max_tokens: int) -> str | None:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        logger.warning("OPENROUTER_API_KEY not set; skipping LLM call")
        return None

    with OpenRouter(api_key=api_key, timeout_ms=int(REQUEST_TIMEOUT_S * 1000)) as client:
        for model in models():
            try:
                return _call_model(client, model, messages, max_tokens=max_tokens)
            except (*SDK_ERRORS, KeyError, IndexError) as exc:
                logger.warning("LLM model %s failed (%s: %s); trying next", model, type(exc).__name__, exc)
                continue

    logger.warning("All LLM models failed")
    return None
