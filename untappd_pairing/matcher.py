import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from untappd_pairing.normalize import clean_beer_name, clean_brewery_name, normalize_for_compare

if TYPE_CHECKING:
    from untappd_pairing.untappd_search import UntappdCandidate

NAME_OVERLAP_WITH_BREWERY = 0.50
BIGRAM_MIN_LEN = 2
STYLE_KEYWORD_MIN_LEN = 3


@dataclass(frozen=True, kw_only=True)
class MatchResult:
    candidate: UntappdCandidate
    score: float
    brewery_matched: bool = False
    # Populated (length > 1) only when several candidates share the top deterministic rank and just
    # rating separates them -- a genuine ambiguity the caller may escalate to the LLM adjudicator.
    tied_candidates: tuple[UntappdCandidate, ...] = ()


def _bigrams(text: str) -> set[str]:
    normalized = normalize_for_compare(text).replace(" ", "")
    if len(normalized) < BIGRAM_MIN_LEN:
        return {normalized} if normalized else set()
    return {normalized[i : i + 2] for i in range(len(normalized) - 1)}


def _overlap_from_bigrams(source_bigrams: set[str], candidate_name: str) -> float:
    candidate_bigrams = _bigrams(candidate_name)
    if not source_bigrams or not candidate_bigrams:
        return 0.0
    return len(source_bigrams & candidate_bigrams) / min(len(source_bigrams), len(candidate_bigrams))


def name_overlap(beer_name: str, candidate_name: str) -> float:
    return _overlap_from_bigrams(_bigrams(clean_beer_name(beer_name)), candidate_name)


_STEM_MIN_LEN = 5


def _stem(token: str) -> str:
    # Czech grammatical case changes a word's ending ("Polička" nominative vs "v Poličce" locative,
    # as in Untappd's own "Měšťanský pivovar v Poličce"). A tap list writes the base form while
    # Untappd's brewery name embeds a declined form, so an exact-token subset check never matches.
    # Trimming the last two characters of longer words compares stems instead of full inflected forms.
    return token[:-2] if len(token) >= _STEM_MIN_LEN else token


def brewery_matches(beer_brewery: str, candidate_brewery: str) -> bool:
    beer_tokens = set(normalize_for_compare(clean_brewery_name(beer_brewery)).split())
    candidate_tokens = set(normalize_for_compare(clean_brewery_name(candidate_brewery)).split())
    if not beer_tokens or not candidate_tokens:
        return False
    # Compare stems so Czech case declension ("Polička" vs "Poličce") doesn't block the subset check.
    beer_stems = {_stem(token) for token in beer_tokens}
    candidate_stems = {_stem(token) for token in candidate_tokens}
    return beer_stems.issubset(candidate_stems)


def _exact_normalized(beer_name: str, candidate_name: str) -> int:
    return int(normalize_for_compare(beer_name) == normalize_for_compare(candidate_name))


def _degree_pattern(degree_plato: float | None) -> re.Pattern[str] | None:
    if degree_plato is None:
        return None
    return re.compile(rf"(?<![\d.]){int(degree_plato)}(?![\d.])(?:\s*°|\s*deg\b)?", re.IGNORECASE)


def _style_keywords(beer_style: str) -> set[str]:
    if not beer_style:
        return set()
    return {w for w in normalize_for_compare(beer_style).split() if len(w) >= STYLE_KEYWORD_MIN_LEN}


def _style_in_name(style_keywords: set[str], candidate_name: str) -> bool:
    if not style_keywords:
        return False
    name_words = set(normalize_for_compare(candidate_name).split())
    return bool(style_keywords & name_words)


def _name_distinct_from_brewery(beer_name: str, beer_brewery: str) -> bool:
    name_tokens = set(normalize_for_compare(clean_beer_name(beer_name)).split())
    brewery_tokens = set(normalize_for_compare(clean_brewery_name(beer_brewery)).split())
    if not name_tokens:
        return False
    return not name_tokens.issubset(brewery_tokens)


_PREFIX_MATCH_MIN_LEN = 4


def _token_explained(token: str, known: set[str]) -> bool:
    # A candidate word is "explained" when the beer name or style already accounts for it. Prefix
    # matching bridges Czech inflection so a descriptor stem covers its longer form ("nefiltr" from
    # style "Nefiltr ležák" explains a candidate's "nefiltrované").
    for word in known:
        if token == word:
            return True
        shorter, longer = (word, token) if len(word) <= len(token) else (token, word)
        if len(shorter) >= _PREFIX_MATCH_MIN_LEN and longer.startswith(shorter):
            return True
    return False


def _extra_qualifier_tokens(beer_name: str, beer_style: str, degree_plato: float | None, candidate_name: str) -> int:
    # Among candidates otherwise tied, the one adding the fewest words beyond what the beer's own
    # name, style and degree already account for is the base product; unexplained extra words mark a
    # variant ("Velikonoční Otakar 11%") that a tap list calling the beer plain "Otakar" does not
    # mean. Style-derived words count as known so a genuinely unfiltered beer still matches its
    # "nefiltrované" listing rather than the plain one.
    known = set(normalize_for_compare(clean_beer_name(beer_name)).split())
    known |= set(normalize_for_compare(beer_style).split())
    degree_token = str(int(degree_plato)) if degree_plato is not None else None
    return sum(
        1
        for token in normalize_for_compare(candidate_name).split()
        if token != degree_token and not _token_explained(token, known)
    )


@dataclass(frozen=True, kw_only=True)
class _Scored:
    overlap: float
    exact: int
    brewery_matched: bool
    degree_match: bool
    style_match: bool
    extra_tokens: int
    candidate: UntappdCandidate


def _rank(scored: _Scored) -> tuple[int, int, float, int, int]:
    # Deterministic discriminators, most significant first. Rating is intentionally excluded:
    # a higher rating does not say which same-named variant the tap list means, so it must not
    # break ties between otherwise-equal candidates -- fewest extra qualifier tokens does.
    return (
        int(scored.degree_match),
        int(scored.style_match),
        scored.overlap,
        scored.exact,
        -scored.extra_tokens,
    )


def best_match(
    beer_name: str,
    beer_brewery: str,
    candidates: list[UntappdCandidate],
    degree_plato: float | None = None,
    beer_style: str = "",
) -> MatchResult | None:
    if not candidates:
        return None

    style_kws = _style_keywords(beer_style)
    degree_re = _degree_pattern(degree_plato)
    name_distinct = _name_distinct_from_brewery(beer_name, beer_brewery)
    source_bigrams = _bigrams(clean_beer_name(beer_name))
    scored = [
        _Scored(
            overlap=_overlap_from_bigrams(source_bigrams, c.name),
            exact=_exact_normalized(beer_name, c.name),
            brewery_matched=brewery_matches(beer_brewery, c.brewery),
            degree_match=degree_re is not None and degree_re.search(c.name) is not None,
            style_match=_style_in_name(style_kws, c.name),
            extra_tokens=_extra_qualifier_tokens(beer_name, beer_style, degree_plato, c.name),
            candidate=c,
        )
        for c in candidates
    ]

    # Only candidates whose brewery matches the source are accepted. A brewery-less name
    # match accepts any same-named beer from a foreign brewery (e.g. "Italian Pilsner" or
    # "Silk Road" from an unrelated brewery), which produced more wrong pairings than right
    # ones; irreconcilable brewery-name divergence is handled by overrides.json instead.
    brewery_hits = [
        s
        for s in scored
        if s.brewery_matched
        and (s.overlap >= NAME_OVERLAP_WITH_BREWERY or s.degree_match or (s.style_match and name_distinct))
    ]
    if not brewery_hits:
        return None

    # Rating stays as the last resort when the deterministic rank cannot separate candidates.
    brewery_hits.sort(key=lambda s: (_rank(s), s.candidate.rating or 0.0), reverse=True)
    top = brewery_hits[0]
    top_rank = _rank(top)
    tied = tuple(s.candidate for s in brewery_hits if _rank(s) == top_rank)
    return MatchResult(
        candidate=top.candidate,
        score=round(top.overlap, 4),
        brewery_matched=True,
        tied_candidates=tied if len(tied) > 1 else (),
    )
