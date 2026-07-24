from untappd_pairing.normalize import (
    build_search_queries,
    clean_beer_name,
    clean_brewery_name,
    normalize_for_compare,
    strip_diacritics,
)


def test_clean_beer_name_strips_degree():
    assert clean_beer_name("Zappa 12°") == "Zappa"
    assert clean_beer_name("Sumeček 11° IPA") == "Sumeček IPA"


def test_clean_beer_name_strips_decimal_degree():
    assert clean_beer_name("12,5° Urban IPA") == "Urban IPA"
    assert clean_beer_name("Hazy 12.5° IPA") == "Hazy IPA"


def test_clean_beer_name_strips_parentheses():
    assert clean_beer_name("Tears of St Laurent (2020)") == "Tears of St Laurent"
    assert clean_beer_name("BA Stout (Bourbon Cask)") == "BA Stout"


def test_clean_beer_name_strips_batch_suffix():
    assert clean_beer_name("DIPA Batch #4") == "DIPA"
    assert clean_beer_name("Sour Vol. 2") == "Sour"
    assert clean_beer_name("Hazy IPA série 12") == "Hazy IPA"


def test_clean_beer_name_keeps_dry_hop_descriptor():
    # clean_beer_name must NOT strip "dry hop" -- it can be a legitimate part of the name. Dropping it
    # is a search fallback handled by build_search_queries, not a blanket cleanup.
    assert clean_beer_name("Cold Fish Mosaic dry hopped") == "Cold Fish Mosaic dry hopped"


def test_clean_beer_name_keeps_style_adjective_and_ingredient_note():
    # Like "dry hop", a generic style adjective and a "+"-joined flavor note can be a legitimate part
    # of the name. Dropping them is a search fallback in build_search_queries, not a blanket cleanup.
    assert clean_beer_name("Ležák světlý") == "Ležák světlý"
    assert (
        clean_beer_name("Fresh Breakfast 001 - meruňka+maracuja+mango")
        == "Fresh Breakfast 001 - meruňka+maracuja+mango"
    )


def test_clean_beer_name_collapses_whitespace():
    assert clean_beer_name("  Foo   Bar  ") == "Foo Bar"


def test_clean_brewery_name_strips_pivovar():
    assert clean_brewery_name("Pivovar Matuška") == "Matuška"
    assert clean_brewery_name("pivovar Falkon") == "Falkon"
    assert clean_brewery_name("Wild Creatures") == "Wild Creatures"


def test_clean_brewery_name_strips_city_suffix():
    assert clean_brewery_name("Haksna, Ostrava") == "Haksna"
    assert clean_brewery_name("Maisel, Bayreuth, Bavorsko") == "Maisel"
    assert clean_brewery_name("Wild Creatures, Mikulov") == "Wild Creatures"
    assert clean_brewery_name("Pivovar Falkon, Praha") == "Falkon"


def test_strip_diacritics():
    assert strip_diacritics("Plzeňský Prazdroj") == "Plzensky Prazdroj"
    assert strip_diacritics("Černý potok") == "Cerny potok"


def test_normalize_for_compare_lowercases_and_strips_diacritics():
    assert normalize_for_compare("Plzeňský  Prazdroj") == "plzensky prazdroj"


def test_normalize_for_compare_strips_punctuation():
    assert normalize_for_compare("Maisel's Weisse") == "maisels weisse"
    assert normalize_for_compare("Tears of St Laurent (2020)") == "tears of st laurent 2020"
    assert normalize_for_compare("Gebr. Maisel") == "gebr maisel"


def test_build_search_queries_prefers_cleaned_form_first():
    queries = build_search_queries("Tears of St Laurent (2020)", "Wild Creatures")
    assert queries[0] == "Tears of St Laurent Wild Creatures"
    assert "Tears of St Laurent (2020) Wild Creatures" in queries
    assert queries[-1] == "Tears of St Laurent"


def test_build_search_queries_adds_dry_hop_stripped_fallback_last():
    queries = build_search_queries("Cold Fish Mosaic dry hopped", "Černý Potoka")
    # The full name (with the process descriptor) is tried first; the stripped form is a fallback.
    assert "Cold Fish Mosaic dry hopped Černý Potoka" in queries
    assert "Cold Fish Mosaic Černý Potoka" in queries
    assert queries.index("Cold Fish Mosaic dry hopped Černý Potoka") < queries.index(
        "Cold Fish Mosaic Černý Potoka",
    )
    # The brewery-less stripped form lands at the very end.
    assert queries[-1] == "Cold Fish Mosaic"


def test_build_search_queries_drops_style_adjective_fallback_last():
    # "Ležák světlý" (Pivovar Hřebec) is "11° Ležák" on Untappd; the generic "světlý" only surfaces
    # unrelated pale lagers, so the style-stripped form is tried as a fallback after the full name.
    queries = build_search_queries("Ležák světlý", "Hřebec", degree_plato=11)
    assert "Ležák světlý 11° Hřebec" in queries
    assert "Ležák 11° Hřebec" in queries
    assert queries.index("Ležák světlý 11° Hřebec") < queries.index("Ležák 11° Hřebec")
    assert queries[-1] == "Ležák"


def test_build_search_queries_drops_trailing_lezak_fallback():
    # "Otakar Ležák" (U Zámastilu) is "Otakar 11%" on Untappd -- unlike "Ležák světlý", here "Ležák"
    # is a trailing style noun appended to the beer's own name, not the name itself.
    queries = build_search_queries("Otakar Ležák", "Polička", degree_plato=11)
    assert "Otakar Ležák 11° Polička" in queries
    assert "Otakar 11° Polička" in queries
    assert queries.index("Otakar Ležák 11° Polička") < queries.index("Otakar 11° Polička")
    assert queries[-1] == "Otakar"


def test_build_search_queries_drops_combined_nefiltr_and_trailing_lezak_fallback():
    # "Záviš Nefiltr Ležák" (U Zámastilu) is "Záviš 12%" on Untappd -- both the abbreviated "Nefiltr"
    # adjective and the trailing "Ležák" noun must strip together to reach the bare name.
    queries = build_search_queries("Záviš Nefiltr Ležák", "Polička", degree_plato=12)
    assert "Záviš Nefiltr Ležák 12° Polička" in queries
    assert "Záviš Ležák 12° Polička" in queries
    assert "Záviš 12° Polička" in queries
    assert queries[-1] == "Záviš"


def test_build_search_queries_drops_trailing_style_phrase_fallback():
    # "Hex Modern Pale Ale" (U Zámastilu, Pivovar Clock) is just "HEX" on Untappd -- the whole style
    # is folded into the tap-list name instead of a separate field.
    queries = build_search_queries("Hex Modern Pale Ale", "Clock", degree_plato=11)
    assert "Hex Modern Pale Ale 11° Clock" in queries
    assert "Hex 11° Clock" in queries
    assert queries.index("Hex Modern Pale Ale 11° Clock") < queries.index("Hex 11° Clock")
    assert queries[-1] == "Hex"

    queries = build_search_queries("Wai-Wai Hazy IPA", "Mazák", degree_plato=12)
    assert "Wai-Wai Hazy IPA 12° Mazák" in queries
    assert "Wai-Wai 12° Mazák" in queries
    assert queries[-1] == "Wai-Wai"


def test_build_search_queries_keeps_style_word_that_is_the_whole_name():
    # A bare style name can legitimately be the entire beer name -- only a *trailing* style phrase
    # appended after something else is dropped.
    queries = build_search_queries("IPA", "")
    assert queries == ["IPA"]
    queries = build_search_queries("Italian Pilsner", "Sibeeria")
    assert all(q != "Italian" for q in queries)


def test_build_search_queries_drops_ingredient_note_fallback():
    # "Fresh Breakfast 001 - meruňka+maracuja+mango" (Louka) is "Fresh Breakfast 001" on Untappd; the
    # full name returns nothing, so the note-stripped form is tried as a fallback.
    queries = build_search_queries("Fresh Breakfast 001 - meruňka+maracuja+mango", "Louka", degree_plato=11)
    assert "Fresh Breakfast 001 - meruňka+maracuja+mango Louka" in queries
    assert "Fresh Breakfast 001 Louka" in queries
    assert queries.index("Fresh Breakfast 001 - meruňka+maracuja+mango Louka") < queries.index(
        "Fresh Breakfast 001 Louka",
    )
    assert queries[-1] == "Fresh Breakfast 001"


def test_build_search_queries_keeps_hyphen_without_plus():
    # A spaced hyphen without a "+"-joined list is not a flavor note -- leave the name intact.
    queries = build_search_queries("Cold Fish - Mosaic", "Falkon")
    assert "Cold Fish - Mosaic Falkon" in queries
    assert all(q != "Cold Fish" for q in queries)


def test_build_search_queries_drops_city_suffix_from_brewery():
    queries = build_search_queries("PP (Pořádné Pivo)", "JungBerg, Hořice")
    assert all("Hořice" not in q for q in queries)
    assert "PP JungBerg" in queries


def test_build_search_queries_dedupes():
    queries = build_search_queries("IPA", "")
    assert queries == ["IPA"]


def test_build_search_queries_drops_empty():
    queries = build_search_queries("12°", "")
    assert queries == ["12°"]


def test_build_search_queries_prefers_degree_variant_first_when_provided():
    queries = build_search_queries("Loutkář", "Loutkář", degree_plato=12)
    assert queries[0] == "Loutkář 12° Loutkář"
    assert "Loutkář 12°" in queries
    assert "Loutkář Loutkář" in queries
    assert "Loutkář" in queries


def test_build_search_queries_tries_all_brewery_variants_before_brewery_less():
    queries = build_search_queries("Italian Pilsner", "Sibeeria, Praha", degree_plato=12)
    assert queries == [
        "Italian Pilsner 12° Sibeeria",
        "Italian Pilsner Sibeeria",
        "Italian Pilsner 12°",
        "Italian Pilsner",
    ]
    # The brewery-qualified no-degree variant must precede the brewery-less degree variant.
    assert queries.index("Italian Pilsner Sibeeria") < queries.index("Italian Pilsner 12°")


def test_build_search_queries_without_degree_unchanged():
    queries = build_search_queries("Loutkář", "Loutkář")
    assert queries == ["Loutkář Loutkář", "Loutkář"]


def test_build_search_queries_truncates_fractional_degree_to_int():
    queries = build_search_queries("Velikonoční", "Loutkář", degree_plato=12.5)
    assert queries[0] == "Velikonoční 12° Loutkář"


def test_build_search_queries_handles_degree_without_brewery():
    queries = build_search_queries("Loutkář", "", degree_plato=11)
    assert queries[0] == "Loutkář 11°"
