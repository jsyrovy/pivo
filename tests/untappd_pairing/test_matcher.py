from untappd_pairing import matcher
from untappd_pairing.untappd_search import UntappdCandidate


def _candidate(name, brewery="Wild Creatures", url="https://untappd.com/b/x/1", rating=4.0):
    return UntappdCandidate(name=name, brewery=brewery, url=url, rating=rating)


def test_name_overlap_full_for_exact_match():
    assert matcher.name_overlap("Tears of St Laurent", "Tears of St Laurent") == 1.0


def test_name_overlap_full_when_short_name_contained_in_long_name():
    assert matcher.name_overlap("JUNO", "Juno 11° Czech Ale") == 1.0
    assert matcher.name_overlap("Velikonoční", "Velikonoční Ležák 12 a Půl") == 1.0


def test_name_overlap_strips_parenthetical_aliases_from_beer_name():
    # tap-api sometimes appends an alias in parens that's not in the Untappd canonical name
    assert matcher.name_overlap("PP (Pořádné Pivo)", "PP 12%") == 1.0


def test_name_overlap_handles_diacritics_and_punctuation():
    assert matcher.name_overlap("Maisels Weisse", "Maisel's Weisse Original") >= 0.85


def test_name_overlap_low_for_different_beers():
    assert matcher.name_overlap("Pilsner", "Stout") < 0.3


def test_name_overlap_zero_when_either_side_normalizes_to_empty():
    assert matcher.name_overlap("", "Pilsner") == 0.0
    assert matcher.name_overlap("Pilsner", "") == 0.0


def test_name_overlap_handles_single_character_name():
    assert matcher.name_overlap("X", "X") == 1.0
    assert matcher.name_overlap("X", "Pilsner") == 0.0


def test_brewery_matches_subset_with_pivovar_prefix():
    assert matcher.brewery_matches("Loutkář", "Pivovar Loutkař") is True


def test_brewery_matches_subset_with_brewery_suffix():
    assert matcher.brewery_matches("Haksna", "Haksna Brewery") is True


def test_brewery_matches_strips_city_suffix_before_comparison():
    assert matcher.brewery_matches("JungBerg, Hořice", "Pivovar JungBerg") is True
    assert matcher.brewery_matches("Maisel, Bayreuth, Bavorsko", "Brauerei Gebr. Maisel") is True


def test_brewery_matches_returns_false_when_disjoint():
    assert matcher.brewery_matches("Loutkář", "Copper Bottom Brewing") is False


def test_brewery_matches_returns_false_when_either_is_empty():
    assert matcher.brewery_matches("", "Pivovar Loutkař") is False
    assert matcher.brewery_matches("Loutkář", "") is False


def test_best_match_prefers_brewery_match_over_higher_name_score():
    copper_bottom = _candidate("Juno", brewery="Copper Bottom Brewing", url="https://untappd.com/b/cb/1")
    loutkar = _candidate("Juno 11° Czech Ale", brewery="Pivovar Loutkař", url="https://untappd.com/b/loutkar/2")
    result = matcher.best_match("JUNO", "Loutkař", [copper_bottom, loutkar])
    assert result is not None
    assert result.candidate.url == "https://untappd.com/b/loutkar/2"
    assert result.brewery_matched is True


def test_best_match_falls_back_to_strict_when_no_brewery_match():
    candidate = _candidate("Tears of St Laurent (2020)", brewery="Wild Creatures Brewery")
    result = matcher.best_match("Tears of St Laurent (2020)", "Unknown Brewery Name", [candidate])
    assert result is not None
    assert result.brewery_matched is False


def test_best_match_returns_none_when_no_brewery_and_loose_name():
    candidate = _candidate("Pilsner Urquell", brewery="Plzeňský Prazdroj")
    result = matcher.best_match("Tears of St Laurent (2020)", "Wild Creatures", [candidate])
    assert result is None


def test_best_match_returns_none_when_brewery_matches_but_name_unrelated():
    candidate = _candidate("Pilsner", brewery="Pivovar Loutkař")
    result = matcher.best_match("Stout", "Loutkař", [candidate])
    assert result is None


def test_best_match_tie_breaker_prefers_higher_rating_within_brewery_tier():
    high = _candidate("Juno", brewery="Pivovar Loutkař", url="https://untappd.com/b/h/1", rating=4.5)
    low = _candidate("Juno", brewery="Pivovar Loutkař", url="https://untappd.com/b/l/2", rating=3.5)
    result = matcher.best_match("Juno", "Loutkař", [low, high])
    assert result is not None
    assert result.candidate.url == "https://untappd.com/b/h/1"


def test_best_match_prefers_exact_normalized_match_over_other_vintage():
    # Same brewery, both names contain the cleaned form, but only one is the exact 2020 vintage
    older = _candidate("Tears of St Laurent (2019)", brewery="Wild Creatures", url="https://untappd.com/b/2019/1")
    matching = _candidate("Tears of St Laurent (2020)", brewery="Wild Creatures", url="https://untappd.com/b/2020/2")
    result = matcher.best_match("Tears of St Laurent (2020)", "Wild Creatures, Mikulov", [older, matching])
    assert result is not None
    assert result.candidate.url == "https://untappd.com/b/2020/2"


def test_best_match_handles_no_candidates():
    assert matcher.best_match("IPA", "Brewery", []) is None


def test_best_match_brewery_path_loose_threshold_accepts_partial_name_overlap():
    candidate = _candidate("Hazy Pale Ale", brewery="Pivovar Falkon")
    result = matcher.best_match("Hazy IPA", "Falkon", [candidate])
    assert result is not None
    assert result.brewery_matched is True


def test_best_match_strict_path_rejects_same_partial_overlap_without_brewery():
    candidate = _candidate("Hazy Pale Ale", brewery="Other Brewery")
    result = matcher.best_match("Hazy IPA", "Falkon", [candidate])
    assert result is None


def test_best_match_accepts_brewery_match_below_threshold_when_degree_matches():
    # Loutkář::Loutkář (deg=12) - Untappd has "Světlý ležák 12" with overlap ~0 vs "Loutkář"
    svetly = _candidate("Světlý ležák 12", brewery="Pivovar Loutkář", url="https://untappd.com/b/x/12")
    result = matcher.best_match("Loutkář", "Loutkář", [svetly], degree_plato=12)
    assert result is not None
    assert result.candidate.url == "https://untappd.com/b/x/12"
    assert result.brewery_matched is True


def test_best_match_picks_correct_degree_among_brewery_match_candidates():
    # Hřebec brewery returns 10°/11°/13° candidates; degree=11 must win even with same overlap
    deg10 = _candidate("10° Summer Ale", brewery="Pivovar Hřebec", url="https://untappd.com/b/x/10", rating=4.5)
    deg11 = _candidate("11° Ležák", brewery="Pivovar Hřebec", url="https://untappd.com/b/x/11", rating=3.5)
    deg13 = _candidate("13° Winter IPA", brewery="Pivovar Hřebec", url="https://untappd.com/b/x/13", rating=4.2)
    result = matcher.best_match("Hřebec", "Hřebec", [deg10, deg11, deg13], degree_plato=11)
    assert result is not None
    assert result.candidate.url == "https://untappd.com/b/x/11"


def test_best_match_degree_match_uses_deg_suffix_form():
    # Untappd writes "11deg" in some URL-slug-derived names
    candidate = _candidate("11deg Lager", brewery="Pivovar Hřebec", url="https://untappd.com/b/x/1")
    result = matcher.best_match("Hřebec", "Hřebec", [candidate], degree_plato=11)
    assert result is not None
    assert result.candidate.url == "https://untappd.com/b/x/1"


def test_best_match_degree_not_in_name_rejects_low_overlap_candidate():
    # Saturn 12 IPL has degree=12 but if we pass degree=11, it must not match
    candidate = _candidate("Saturn 12 IPL", brewery="Pivovar Loutkář", url="https://untappd.com/b/x/saturn")
    result = matcher.best_match("Loutkář", "Loutkář", [candidate], degree_plato=11)
    assert result is None


def test_best_match_without_degree_unchanged_behavior():
    candidate = _candidate("Světlý ležák 12", brewery="Pivovar Loutkář")
    result = matcher.best_match("Loutkář", "Loutkář", [candidate])
    assert result is None


def test_best_match_degree_does_not_match_substring_of_larger_number():
    # candidate has "120" - must not match degree=12 (avoid spurious substring hits)
    candidate = _candidate("Special 120 Edition", brewery="Pivovar Loutkář", url="https://untappd.com/b/x/120")
    result = matcher.best_match("Loutkář", "Loutkář", [candidate], degree_plato=12)
    assert result is None


def test_best_match_int_degree_does_not_match_fractional_in_name():
    # degree=11 (int from 11.0) must NOT match candidate "11.5° Lager" - fractional is different beer
    candidate = _candidate("11.5° Lager", brewery="Pivovar Hřebec", url="https://untappd.com/b/x/115")
    result = matcher.best_match("Hřebec", "Hřebec", [candidate], degree_plato=11)
    assert result is None


def test_best_match_style_wins_over_higher_rated_other_style():
    # Loutkář brewery returns multiple 12° beers; style "Ležák světlý" must pick the lager
    paraganska = _candidate(
        "Paragánská 12 Single Beer",
        brewery="Pivovar Loutkář",
        url="https://untappd.com/b/x/paraganska",
        rating=4.5,
    )
    lezak = _candidate("Světlý ležák 12", brewery="Pivovar Loutkář", url="https://untappd.com/b/x/lezak", rating=3.5)
    saturn = _candidate("Saturn 12 IPL", brewery="Pivovar Loutkář", url="https://untappd.com/b/x/saturn", rating=4.2)
    result = matcher.best_match(
        "Loutkář",
        "Loutkář",
        [paraganska, lezak, saturn],
        degree_plato=12,
        beer_style="Ležák světlý",
    )
    assert result is not None
    assert result.candidate.url == "https://untappd.com/b/x/lezak"


def test_best_match_style_picks_lezak_over_apa_for_hrebec():
    # Hřebec returns 11° APA and 11° Ležák; style "Ležák světlý" picks Ležák
    apa = _candidate("11° American Pale Ale", brewery="Pivovar Hřebec", url="https://untappd.com/b/x/apa", rating=4.0)
    lezak = _candidate("11° Ležák", brewery="Pivovar Hřebec", url="https://untappd.com/b/x/lezak11", rating=3.5)
    result = matcher.best_match("Hřebec", "Hřebec", [apa, lezak], degree_plato=11, beer_style="Ležák světlý")
    assert result is not None
    assert result.candidate.url == "https://untappd.com/b/x/lezak11"


def test_best_match_style_alone_cannot_rescue_without_degree_or_overlap():
    pale = _candidate("Hazy Pale Ale", brewery="Pivovar Falkon", url="https://untappd.com/b/x/pale")
    stout = _candidate("Imperial Stout", brewery="Pivovar Falkon", url="https://untappd.com/b/x/stout")
    result = matcher.best_match("Falkon", "Falkon", [pale, stout], degree_plato=15, beer_style="Imperial Stout")
    assert result is None


def test_best_match_style_rescues_brewery_match_when_name_translated_to_english():
    # Klenot::Pomeranč + skořice (Sour, 10°) -- Untappd has the English-translated name
    # "Sour ALE Orange Cinnamon" under "Hradecký Klenot". Brewery is a subset match, style
    # "Sour" appears in the candidate name, and source name is informative beyond the brewery.
    klenot = _candidate(
        "Sour ALE- Orange & Cinnamon",
        brewery="Hradecký Klenot",
        url="https://untappd.com/b/klenot/sour",
    )
    cestmir = _candidate(
        "Vánoční Sour Pomeranč Skořice",
        brewery="Pivovar Čestmír",
        url="https://untappd.com/b/cestmir/sour",
    )
    result = matcher.best_match(
        "Pomeranč + skořice",
        "Klenot",
        [klenot, cestmir],
        degree_plato=10,
        beer_style="Sour",
    )
    assert result is not None
    assert result.candidate.url == "https://untappd.com/b/klenot/sour"
    assert result.brewery_matched is True


def test_best_match_strict_path_rejects_short_generic_source_name():
    # "Helles" has 5 bigrams; bigram overlap=1.0 against any longer candidate name containing
    # "helles" is misleading. Without a brewery match, the matcher must not accept it -- otherwise
    # generic style-like names match wrong-brewery beers and short-circuit later queries.
    dva_kohouti = _candidate("Místní Helles 11°", brewery="Dva kohouti", url="https://untappd.com/b/dk/1")
    wywar = _candidate("11° Helles", brewery="Holíčsky pivovar Wywar", url="https://untappd.com/b/w/2")
    result = matcher.best_match("Helles", "Louka", [dva_kohouti, wywar], degree_plato=11)
    assert result is None


def test_best_match_brewery_path_still_works_for_short_source_name():
    # Same short name "Helles", but candidate brewery matches -- must still pair.
    louka = _candidate("Helles", brewery="Pivovar Louka", url="https://untappd.com/b/louka/h", rating=3.5)
    result = matcher.best_match("Helles", "Louka", [louka], degree_plato=11)
    assert result is not None
    assert result.candidate.url == "https://untappd.com/b/louka/h"
    assert result.brewery_matched is True


def test_best_match_style_does_not_rescue_when_name_is_just_brewery():
    # Source name equals brewery -- name carries no info beyond the brewery, so style-only
    # rescue must not fire (preserves the Falkon::Falkon "no real beer name" semantics).
    stout = _candidate("Imperial Stout", brewery="Pivovar Falkon", url="https://untappd.com/b/x/stout")
    result = matcher.best_match("Falkon", "Falkon", [stout], beer_style="Imperial Stout")
    assert result is None
