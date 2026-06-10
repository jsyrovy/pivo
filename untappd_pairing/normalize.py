import re
import unicodedata

_DEGREE_RE = re.compile(r"\d+(?:[.,]\d+)?\s*°")
_PARENS_RE = re.compile(r"\([^)]*\)")
_BATCH_RE = re.compile(r"\b(?:batch|vol\.?|série|serie)\s*#?\s*\d+", re.IGNORECASE)
# "Dry hop(ped)" is often a brewing-process descriptor a tap list appends ("Cold Fish Mosaic dry
# hopped") that Untappd keeps terse ("Cold Fish - Mosaic Dry Hop"), blocking the search. But it can
# also be a legitimate part of the name, so build_search_queries only tries the stripped form as a
# fallback after the full name (and its other variants) found nothing.
_DRYHOP_RE = re.compile(r"\b(?:(?:double|triple) )?dry[ -]?hop(?:ped|s)?\b", re.IGNORECASE)
# A generic Czech style adjective a tap list appends ("Ležák světlý") that the Untappd entry often
# omits ("11° Ležák"), so the full name surfaces only unrelated pale lagers. Like the dry-hop
# descriptor it can be a legitimate part of the name, so it is dropped only as a search fallback.
_STYLE_ADJECTIVE_RE = re.compile(
    r"\b(?:světl|polotmav|tmav|řezan|nefiltrovan|kvasnicov|čern)[ýáé]\b",
    re.IGNORECASE,
)
# A trailing " - <ingredients>" flavor note a tap list appends, where the ingredients are joined by
# "+" ("Fresh Breakfast 001 - meruňka+maracuja+mango", "Silk Road - ibišek+koriandr+limeta+yuzu").
# Untappd keeps the bare name ("Fresh Breakfast 001"). The "+"-joined list is a strong signal this
# is a note rather than part of the name, so it is dropped only as a search fallback.
_INGREDIENT_NOTE_RE = re.compile(r"\s+-\s+.*\+.*$")
_WHITESPACE_RE = re.compile(r"\s+")
_APOSTROPHE_RE = re.compile(r"[\u2019']")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9 ]")


def strip_diacritics(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return decomposed.encode("ascii", "ignore").decode("ascii")


def clean_beer_name(name: str) -> str:
    cleaned = _DEGREE_RE.sub(" ", name)
    cleaned = _PARENS_RE.sub(" ", cleaned)
    cleaned = _BATCH_RE.sub(" ", cleaned)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned)
    return cleaned.strip()


def clean_brewery_name(brewery: str) -> str:
    primary = brewery.split(",", 1)[0]
    cleaned = re.sub(r"\bpivovar\b", "", primary, flags=re.IGNORECASE)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned)
    return cleaned.strip()


def normalize_for_compare(text: str) -> str:
    stripped = strip_diacritics(text).lower()
    stripped = _APOSTROPHE_RE.sub("", stripped)
    stripped = _NON_ALNUM_RE.sub(" ", stripped)
    return _WHITESPACE_RE.sub(" ", stripped).strip()


def _append_variants(candidates: list[str], name: str, brewery: str, degree: str | None) -> None:
    # Every brewery-qualified variant is appended before any brewery-less one: the brewery
    # is the strongest disambiguator, so a brewery-less query must never win first.
    if brewery:
        if degree is not None:
            candidates.append(f"{name} {degree} {brewery}")
        candidates.append(f"{name} {brewery}")
    if degree is not None:
        candidates.append(f"{name} {degree}")
    candidates.append(name)


def build_search_queries(name: str, brewery: str, degree_plato: float | None = None) -> list[str]:
    raw_name = name.strip()
    raw_brewery = brewery.strip()
    cleaned_name = clean_beer_name(raw_name)
    cleaned_brewery = clean_brewery_name(raw_brewery)

    degree = f"{int(degree_plato)}°" if degree_plato is not None else None

    # Every brewery-qualified variant is tried before any brewery-less one: the brewery
    # is the strongest disambiguator, so a brewery-less query must never win first.
    candidates: list[str] = []
    if cleaned_brewery:
        if degree is not None:
            candidates.append(f"{cleaned_name} {degree} {cleaned_brewery}")
        candidates.append(f"{cleaned_name} {cleaned_brewery}")
        candidates.append(f"{raw_name} {cleaned_brewery}")
    if degree is not None:
        candidates.append(f"{cleaned_name} {degree}")
    candidates.append(cleaned_name)
    if not cleaned_brewery:
        candidates.append(raw_name)

    # Last-resort fallbacks: each drops a different descriptor the tap list appends but Untappd omits
    # (brewing process, generic style adjective, "+"-joined ingredient note). Appended after every
    # full-name variant so a beer that legitimately carries the descriptor still wins earlier; the
    # brewery-gated matcher filters out any noise these broader queries surface.
    for descriptor_re in (_DRYHOP_RE, _STYLE_ADJECTIVE_RE, _INGREDIENT_NOTE_RE):
        stripped = _WHITESPACE_RE.sub(" ", descriptor_re.sub(" ", cleaned_name)).strip()
        if stripped and stripped != cleaned_name:
            _append_variants(candidates, stripped, cleaned_brewery, degree)

    queries: list[str] = []
    for candidate in candidates:
        normalized = _WHITESPACE_RE.sub(" ", candidate).strip()
        if normalized and normalized not in queries:
            queries.append(normalized)
    return queries
