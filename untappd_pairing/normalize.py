import re
import unicodedata

_DEGREE_RE = re.compile(r"\d+(?:[.,]\d+)?\s*°")
_PARENS_RE = re.compile(r"\([^)]*\)")
_BATCH_RE = re.compile(r"\b(?:batch|vol\.?|série|serie)\s*#?\s*\d+", re.IGNORECASE)
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


def build_search_queries(name: str, brewery: str, degree_plato: float | None = None) -> list[str]:
    raw_name = name.strip()
    raw_brewery = brewery.strip()
    cleaned_name = clean_beer_name(raw_name)
    cleaned_brewery = clean_brewery_name(raw_brewery)

    candidates: list[str] = []
    if degree_plato is not None:
        degree = f"{int(degree_plato)}°"
        if cleaned_brewery:
            candidates.append(f"{cleaned_name} {degree} {cleaned_brewery}".strip())
        candidates.append(f"{cleaned_name} {degree}".strip())
    candidates.extend(
        [
            f"{cleaned_name} {cleaned_brewery}".strip() if cleaned_brewery else cleaned_name,
            f"{raw_name} {cleaned_brewery}".strip() if cleaned_brewery else raw_name,
            cleaned_name,
        ],
    )

    queries: list[str] = []
    for candidate in candidates:
        normalized = _WHITESPACE_RE.sub(" ", candidate).strip()
        if normalized and normalized not in queries:
            queries.append(normalized)
    return queries
