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


def test_clean_beer_name_strips_parentheses():
    assert clean_beer_name("Tears of St Laurent (2020)") == "Tears of St Laurent"
    assert clean_beer_name("BA Stout (Bourbon Cask)") == "BA Stout"


def test_clean_beer_name_strips_batch_suffix():
    assert clean_beer_name("DIPA Batch #4") == "DIPA"
    assert clean_beer_name("Sour Vol. 2") == "Sour"
    assert clean_beer_name("Hazy IPA série 12") == "Hazy IPA"


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


def test_build_search_queries_without_degree_unchanged():
    queries = build_search_queries("Loutkář", "Loutkář")
    assert queries == ["Loutkář Loutkář", "Loutkář"]


def test_build_search_queries_truncates_fractional_degree_to_int():
    queries = build_search_queries("Velikonoční", "Loutkář", degree_plato=12.5)
    assert queries[0] == "Velikonoční 12° Loutkář"


def test_build_search_queries_handles_degree_without_brewery():
    queries = build_search_queries("Loutkář", "", degree_plato=11)
    assert queries[0] == "Loutkář 11°"
