from pathlib import Path

import pytest

from dvdcompare.parser import (
    _extract_format,
    _extract_year,
    format_runtime,
    parse_extras,
    parse_feature_line,
    parse_film_page,
    parse_runtime,
    parse_search_results,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def oppenheimer_html():
    return (FIXTURES / "oppenheimer_4k.html").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# parse_runtime
# ---------------------------------------------------------------------------


class TestParseRuntime:
    def test_mm_ss(self):
        assert parse_runtime("87:18") == 87 * 60 + 18

    def test_short_mm_ss(self):
        assert parse_runtime("7:17") == 7 * 60 + 17

    def test_h_mm_ss(self):
        assert parse_runtime("1:30:00") == 5400

    def test_single_digit_seconds(self):
        assert parse_runtime("2:04") == 124


class TestFormatRuntime:
    def test_under_one_hour(self):
        assert format_runtime(87 * 60 + 18) == "1:27:18"

    def test_over_one_hour(self):
        assert format_runtime(5400) == "1:30:00"

    def test_short(self):
        assert format_runtime(71) == "1:11"


# ---------------------------------------------------------------------------
# parse_feature_line
# ---------------------------------------------------------------------------


class TestParseFeatureLine:
    def test_quoted_with_year_type_runtime(self):
        line = (
            '"To End All War: Oppenheimer & the Atomic Bomb"'
            " 2023 documentary (87:18)"
        )
        f = parse_feature_line(line)
        assert f.title == "To End All War: Oppenheimer & the Atomic Bomb"
        assert f.year == 2023
        assert f.feature_type == "documentary"
        assert f.runtime_seconds == 87 * 60 + 18
        assert not f.is_play_all
        assert f.children == []

    def test_play_all_group_with_colon(self):
        line = (
            '"The Story of Our Time: The Making of Oppenheimer"'
            " 2023 documentary (Play All - 72:25):"
        )
        f = parse_feature_line(line)
        assert f.title == "The Story of Our Time: The Making of Oppenheimer"
        assert f.year == 2023
        assert f.feature_type == "documentary"
        assert f.runtime_seconds == 72 * 60 + 25
        assert f.is_play_all

    def test_technical_notes(self):
        line = (
            '"Meet the Press Q&A Panel: Oppenheimer"'
            " 2023 interviews (34:46) [1080i/60]"
        )
        f = parse_feature_line(line)
        assert f.title == "Meet the Press Q&A Panel: Oppenheimer"
        assert f.runtime_seconds == 34 * 60 + 46
        assert f.technical_notes == "1080i/60"
        assert f.year == 2023
        assert f.feature_type == "interviews"

    def test_unquoted_play_all(self):
        f = parse_feature_line("Trailers (Play All - 14:11):")
        assert f.title == "Trailers"
        assert f.runtime_seconds == 14 * 60 + 11
        assert f.is_play_all

    def test_simple_unquoted_with_runtime(self):
        f = parse_feature_line("Teaser (1:11)")
        assert f.title == "Teaser"
        assert f.runtime_seconds == 71

    def test_unquoted_with_number(self):
        f = parse_feature_line("Trailer 2 (2:04)")
        assert f.title == "Trailer 2"
        assert f.runtime_seconds == 124

    def test_simple_quoted_with_runtime(self):
        f = parse_feature_line('"Now I Am Become Death" (7:17)')
        assert f.title == "Now I Am Become Death"
        assert f.runtime_seconds == 7 * 60 + 17
        assert f.year is None
        assert f.feature_type is None

    def test_whitespace_normalized(self):
        f = parse_feature_line('"To End All War:  Oppenheimer" (10:00)')
        assert f.title == "To End All War: Oppenheimer"


# ---------------------------------------------------------------------------
# parse_extras
# ---------------------------------------------------------------------------


class TestParseExtras:
    def test_three_discs(self):
        html = (
            '<b>DISC ONE (Blu-ray 4K)</b><br>* The Film<br><br>'
            '<b>DISC TWO (Blu-ray)</b><br>* The Film<br><br>'
            '<b>DISC THREE (Blu-ray)</b><br>'
            '"Some Feature" (10:00)'
        )
        discs = parse_extras(html)
        assert len(discs) == 3
        assert discs[0].number == 1
        assert discs[0].format == "Blu-ray 4K"
        assert discs[0].is_film is True
        assert discs[1].number == 2
        assert discs[1].is_film is True
        assert discs[2].number == 3
        assert discs[2].is_film is False
        assert len(discs[2].features) == 1

    def test_group_with_children(self):
        html = (
            "<b>DISC ONE (Blu-ray)</b><br>"
            "Making Of (Play All - 20:00):<br>"
            '- "Part 1" (10:00)<br>'
            '- "Part 2" (10:00)<br>'
            '"Standalone Feature" (5:00)'
        )
        discs = parse_extras(html)
        disc = discs[0]
        assert len(disc.features) == 2

        group = disc.features[0]
        assert group.title == "Making Of"
        assert group.is_play_all is True
        assert group.runtime_seconds == 20 * 60
        assert len(group.children) == 2
        assert group.children[0].title == "Part 1"
        assert group.children[1].title == "Part 2"

        standalone = disc.features[1]
        assert standalone.title == "Standalone Feature"
        assert standalone.children == []

    def test_anchor_tags_stripped(self):
        html = (
            '<a name="1"><b>DISC ONE (Blu-ray 4K)</b><br>* The Film<br></a>'
            '<a href="film.php?fid=66398"><b>DISC TWO (Blu-ray)</b></a>'
            "<br>* The Film"
        )
        discs = parse_extras(html)
        assert len(discs) == 2
        assert discs[0].format == "Blu-ray 4K"
        assert discs[0].is_film is True
        assert discs[1].format == "Blu-ray"
        assert discs[1].is_film is True

    def test_asterisk_variant_with_suffix(self):
        """Asterisk film markers with variant titles set is_film and keep the feature."""
        html = (
            '<b>DISC ONE (Blu-ray 4K)</b><br>'
            '*The Film - Theatrical Cut (2:15:07)<br>'
            '<b>DISC TWO (Blu-ray)</b><br>'
            '* The Film - US TV Cut (1080p/English DTS 5.1)<br>'
        )
        discs = parse_extras(html)
        assert discs[0].is_film is True
        assert len(discs[0].features) == 1
        assert discs[0].features[0].title == "The Film - Theatrical Cut"
        assert discs[0].features[0].runtime_seconds == 2 * 3600 + 15 * 60 + 7
        assert discs[1].is_film is True
        assert len(discs[1].features) == 1
        assert discs[1].features[0].title == 'The Film - US TV Cut (1080p/English DTS 5.1)'


# ---------------------------------------------------------------------------
# parse_film_page  (full integration with fixture)
# ---------------------------------------------------------------------------


class TestParseFilmPage:
    def test_title(self, oppenheimer_html):
        film = parse_film_page(oppenheimer_html)
        assert film.title == "Oppenheimer"

    def test_year(self, oppenheimer_html):
        film = parse_film_page(oppenheimer_html)
        assert film.year == 2023

    def test_format(self, oppenheimer_html):
        film = parse_film_page(oppenheimer_html)
        assert film.format == "Blu-ray 4K"

    def test_director(self, oppenheimer_html):
        film = parse_film_page(oppenheimer_html)
        assert film.director == "Christopher Nolan"

    def test_imdb_id(self, oppenheimer_html):
        film = parse_film_page(oppenheimer_html)
        assert film.imdb_id == "tt15398776"

    def test_imdb_url(self, oppenheimer_html):
        film = parse_film_page(oppenheimer_html)
        assert "imdb.com/title/tt15398776" in film.imdb_url

    def test_film_id(self, oppenheimer_html):
        film = parse_film_page(oppenheimer_html)
        assert film.film_id == 66397

    def test_release_count(self, oppenheimer_html):
        film = parse_film_page(oppenheimer_html)
        assert len(film.releases) == 2

    def test_america_release_name(self, oppenheimer_html):
        film = parse_film_page(oppenheimer_html)
        r = film.releases[0]
        assert "America" in r.name
        assert "Universal Pictures" in r.name

    def test_america_release_year(self, oppenheimer_html):
        film = parse_film_page(oppenheimer_html)
        assert film.releases[0].year == 2023

    def test_japan_release_year(self, oppenheimer_html):
        film = parse_film_page(oppenheimer_html)
        assert film.releases[1].year == 2024

    def test_three_discs(self, oppenheimer_html):
        film = parse_film_page(oppenheimer_html)
        discs = film.releases[0].discs
        assert len(discs) == 3

    def test_disc_one_is_film(self, oppenheimer_html):
        film = parse_film_page(oppenheimer_html)
        d = film.releases[0].discs[0]
        assert d.number == 1
        assert d.format == "Blu-ray 4K"
        assert d.is_film is True
        assert len(d.features) == 0

    def test_disc_two_is_film(self, oppenheimer_html):
        film = parse_film_page(oppenheimer_html)
        d = film.releases[0].discs[1]
        assert d.number == 2
        assert d.format == "Blu-ray"
        assert d.is_film is True

    def test_disc_three_has_five_features(self, oppenheimer_html):
        film = parse_film_page(oppenheimer_html)
        d = film.releases[0].discs[2]
        assert d.number == 3
        assert d.format == "Blu-ray"
        assert d.is_film is False
        assert len(d.features) == 5

    def test_to_end_all_war(self, oppenheimer_html):
        film = parse_film_page(oppenheimer_html)
        f = film.releases[0].discs[2].features[0]
        assert "To End All War" in f.title
        assert "Oppenheimer" in f.title
        assert f.runtime_seconds == 87 * 60 + 18
        assert f.year == 2023
        assert f.feature_type == "documentary"
        assert f.children == []

    def test_making_of_group(self, oppenheimer_html):
        film = parse_film_page(oppenheimer_html)
        f = film.releases[0].discs[2].features[1]
        assert "Story of Our Time" in f.title
        assert f.is_play_all is True
        assert f.runtime_seconds == 72 * 60 + 25
        assert len(f.children) == 7

    def test_making_of_children_titles(self, oppenheimer_html):
        film = parse_film_page(oppenheimer_html)
        children = film.releases[0].discs[2].features[1].children
        expected = [
            "Now I Am Become Death",
            "The Luminaries",
            "The Manhattan Project",
            "The Devil of the Details",
            "Walking a Mile",
            "Can You Hear the Music?",
            "We Can Perform This Miracle",
        ]
        assert [c.title for c in children] == expected

    def test_making_of_first_child_runtime(self, oppenheimer_html):
        film = parse_film_page(oppenheimer_html)
        child = film.releases[0].discs[2].features[1].children[0]
        assert child.runtime_seconds == 7 * 60 + 17

    def test_meet_the_press(self, oppenheimer_html):
        film = parse_film_page(oppenheimer_html)
        f = film.releases[0].discs[2].features[2]
        assert "Meet the Press" in f.title
        assert f.runtime_seconds == 34 * 60 + 46
        assert f.technical_notes == "1080i/60"
        assert f.feature_type == "interviews"

    def test_innovations(self, oppenheimer_html):
        film = parse_film_page(oppenheimer_html)
        f = film.releases[0].discs[2].features[3]
        assert "Innovations in Film" in f.title
        assert f.runtime_seconds == 8 * 60 + 21
        assert f.feature_type == "featurette"

    def test_trailers_group(self, oppenheimer_html):
        film = parse_film_page(oppenheimer_html)
        f = film.releases[0].discs[2].features[4]
        assert f.title == "Trailers"
        assert f.is_play_all is True
        assert f.runtime_seconds == 14 * 60 + 11
        assert len(f.children) == 5

    def test_trailer_children(self, oppenheimer_html):
        film = parse_film_page(oppenheimer_html)
        children = film.releases[0].discs[2].features[4].children
        assert children[0].title == "Teaser"
        assert children[0].runtime_seconds == 71
        assert children[1].title == "Trailer 2"
        assert children[4].title == "Opening Look"
        assert children[4].runtime_seconds == 5 * 60 + 7

    def test_japan_different_trailer_runtime(self, oppenheimer_html):
        film = parse_film_page(oppenheimer_html)
        japan = film.releases[1]
        assert "Japan" in japan.name
        trailers = japan.discs[2].features[4]
        assert trailers.runtime_seconds == 14 * 60 + 12
        # Japan has Opening Look at 5:09 vs 5:07
        assert trailers.children[4].runtime_seconds == 5 * 60 + 9


# ---------------------------------------------------------------------------
# parse_runtime  -- "NNN mins" format
# ---------------------------------------------------------------------------


class TestParseRuntimeMins:
    def test_mins_format(self):
        assert parse_runtime("181 mins") == 181 * 60

    def test_min_singular(self):
        assert parse_runtime("60 min") == 3600

    def test_mins_with_extra_space(self):
        assert parse_runtime("  120 mins  ") == 7200


# ---------------------------------------------------------------------------
# parse_feature_line  -- "with Play All option" pattern
# ---------------------------------------------------------------------------


class TestParseFeatureLinePlayAllOption:
    def test_with_play_all_option_mmss(self):
        f = parse_feature_line("Episodes (with Play All option - 154:35)")
        assert f.title == "Episodes"
        assert f.is_play_all is True
        assert f.runtime_seconds == 154 * 60 + 35

    def test_with_play_all_option_mins(self):
        f = parse_feature_line("Episodes (with Play All option - 181 mins)")
        assert f.title == "Episodes"
        assert f.is_play_all is True
        assert f.runtime_seconds == 181 * 60

    def test_child_with_mins_runtime(self):
        f = parse_feature_line('"Coasts" (61 mins)')
        assert f.title == "Coasts"
        assert f.runtime_seconds == 61 * 60

    def test_behind_the_scenes_montage(self):
        f = parse_feature_line(
            '"Making of Planet Earth III" behind-the-scenes montage (54:15)'
        )
        assert f.title == "Making of Planet Earth III"
        assert f.feature_type == "behind-the-scenes montage"
        assert f.runtime_seconds == 54 * 60 + 15


# ---------------------------------------------------------------------------
# parse_film_page  -- Planet Earth III fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def planet_earth_html():
    return (FIXTURES / "planet_earth_iii_4k.html").read_text(encoding="utf-8")


class TestParseFilmPagePlanetEarth:
    def test_title(self, planet_earth_html):
        film = parse_film_page(planet_earth_html)
        assert film.title == "Planet Earth III (TV)"

    def test_year(self, planet_earth_html):
        film = parse_film_page(planet_earth_html)
        assert film.year == 2023

    def test_format(self, planet_earth_html):
        film = parse_film_page(planet_earth_html)
        assert film.format == "Blu-ray 4K"

    def test_director(self, planet_earth_html):
        film = parse_film_page(planet_earth_html)
        assert "Nick Easton" in film.director
        assert "Steve Greenwood" in film.director

    def test_imdb_id(self, planet_earth_html):
        film = parse_film_page(planet_earth_html)
        assert film.imdb_id == "tt9805674"

    def test_film_id(self, planet_earth_html):
        film = parse_film_page(planet_earth_html)
        assert film.film_id == 67210

    def test_release_count(self, planet_earth_html):
        film = parse_film_page(planet_earth_html)
        assert len(film.releases) == 2

    def test_america_release(self, planet_earth_html):
        film = parse_film_page(planet_earth_html)
        r = film.releases[0]
        assert "America" in r.name
        assert r.year == 2024

    def test_uk_release(self, planet_earth_html):
        film = parse_film_page(planet_earth_html)
        r = film.releases[1]
        assert "United Kingdom" in r.name
        assert r.year == 2024

    def test_america_six_discs(self, planet_earth_html):
        film = parse_film_page(planet_earth_html)
        discs = film.releases[0].discs
        assert len(discs) == 6

    def test_disc_one_4k_episodes(self, planet_earth_html):
        film = parse_film_page(planet_earth_html)
        d = film.releases[0].discs[0]
        assert d.number == 1
        assert d.format == "Blu-ray 4K"
        assert d.is_film is False
        assert len(d.features) == 1
        ep = d.features[0]
        assert ep.title == "Episodes"
        assert ep.is_play_all is True
        assert ep.runtime_seconds == 154 * 60 + 35
        assert len(ep.children) == 3

    def test_disc_one_episode_titles(self, planet_earth_html):
        film = parse_film_page(planet_earth_html)
        children = film.releases[0].discs[0].features[0].children
        assert children[0].title == "Coasts"
        assert children[0].runtime_seconds == 52 * 60 + 21
        assert children[1].title == "Ocean"
        assert children[1].runtime_seconds == 52 * 60 + 30
        assert children[2].title == "Deserts & Grasslands"
        assert children[2].runtime_seconds == 49 * 60 + 43

    def test_disc_two_episodes(self, planet_earth_html):
        film = parse_film_page(planet_earth_html)
        d = film.releases[0].discs[1]
        assert d.number == 2
        assert d.format == "Blu-ray 4K"
        ep = d.features[0]
        assert ep.runtime_seconds == 154 * 60 + 19
        assert len(ep.children) == 3
        assert ep.children[0].title == "Freshwater"
        assert ep.children[1].title == "Forests"
        assert ep.children[2].title == "Extremes"

    def test_disc_three_episodes_plus_making_of(self, planet_earth_html):
        film = parse_film_page(planet_earth_html)
        d = film.releases[0].discs[2]
        assert d.number == 3
        assert d.format == "Blu-ray 4K"
        assert len(d.features) == 2

        ep = d.features[0]
        assert ep.title == "Episodes"
        assert ep.runtime_seconds == 105 * 60 + 46
        assert len(ep.children) == 2
        assert ep.children[0].title == "Human"
        assert ep.children[1].title == "Heroes"

        making = d.features[1]
        assert making.title == "Making of Planet Earth III"
        assert making.feature_type == "behind-the-scenes montage"
        assert making.runtime_seconds == 54 * 60 + 15


# ---------------------------------------------------------------------------
# _extract_year / _extract_format
# ---------------------------------------------------------------------------


class TestExtractYear:
    def test_trailing_year(self):
        assert _extract_year("King Kong                         (2005)") == 2005

    def test_format_and_year(self):
        assert _extract_year("King Kong (Blu-ray 4K)                           (2005)") == 2005

    def test_no_year(self):
        assert _extract_year("King Kong") is None

    def test_year_in_middle_ignored(self):
        # Year must be at the end
        assert _extract_year("King Kong (2005) extras") is None


class TestExtractFormat:
    def test_bluray_4k(self):
        assert _extract_format("King Kong (Blu-ray 4K)                           (2005)") == "Blu-ray 4K"

    def test_bluray(self):
        assert _extract_format("King Kong (Blu-ray)                              (2005)") == "Blu-ray"

    def test_dvd(self):
        assert _extract_format("King Kong (DVD)                                  (2005)") == "DVD"

    def test_hd_dvd(self):
        assert _extract_format("King Kong (HD DVD)                               (2005)") == "HD DVD"

    def test_no_format(self):
        assert _extract_format("King Kong                         (2005)") is None

    def test_non_format_parens_ignored(self):
        # "(TV)" is not a known format
        assert _extract_format("King of Christmas (The) AKA Julekongen (TV)  (2012)") is None


class TestParseFilmPagePlanetEarthDiscs:
    """Remaining Planet Earth disc tests (continuation)."""

    def test_disc_four_bluray_mins(self, planet_earth_html):
        film = parse_film_page(planet_earth_html)
        d = film.releases[0].discs[3]
        assert d.number == 4
        assert d.format == "Blu-ray"
        ep = d.features[0]
        assert ep.is_play_all is True
        assert ep.runtime_seconds == 181 * 60
        assert len(ep.children) == 3
        assert ep.children[0].title == "Coasts"
        assert ep.children[0].runtime_seconds == 61 * 60
        assert ep.children[1].runtime_seconds == 60 * 60
        assert ep.children[2].runtime_seconds == 60 * 60

    def test_disc_five_bluray(self, planet_earth_html):
        film = parse_film_page(planet_earth_html)
        d = film.releases[0].discs[4]
        assert d.number == 5
        assert d.format == "Blu-ray"
        ep = d.features[0]
        assert ep.runtime_seconds == 179 * 60
        assert len(ep.children) == 3

    def test_disc_six_bluray(self, planet_earth_html):
        film = parse_film_page(planet_earth_html)
        d = film.releases[0].discs[5]
        assert d.number == 6
        assert d.format == "Blu-ray"
        ep = d.features[0]
        assert ep.runtime_seconds == 120 * 60
        assert len(ep.children) == 2

    def test_uk_disc_four_different_runtimes(self, planet_earth_html):
        film = parse_film_page(planet_earth_html)
        uk = film.releases[1]
        d = uk.discs[3]
        assert d.number == 4
        ep = d.features[0]
        assert ep.runtime_seconds == 173 * 60 + 54
        assert ep.children[0].title == "Coasts"
        assert ep.children[0].runtime_seconds == 58 * 60 + 25

    def test_uk_disc_six(self, planet_earth_html):
        film = parse_film_page(planet_earth_html)
        uk = film.releases[1]
        d = uk.discs[5]
        ep = d.features[0]
        assert ep.runtime_seconds == 115 * 60 + 1
        assert ep.children[1].title == "Heroes"
        assert ep.children[1].runtime_seconds == 57 * 60 + 49


# ---------------------------------------------------------------------------
# parse_search_results
# ---------------------------------------------------------------------------


class TestParseSearchResults:
    def test_multi_result_links(self):
        html = """<html><body>
        <a href="film.php?fid=100">Film A (2020)</a>
        <a href="film.php?fid=200">Film B (2021)</a>
        </body></html>"""
        results = parse_search_results(html)
        assert len(results) == 2
        assert results[0].film_id == 100
        assert results[1].film_id == 200

    def test_js_redirect_single_result(self):
        html = """<html><body>
        <SCRIPT LANGUAGE="Javascript">
        <!--
        location.href="film.php?fid=23028";
        //--></SCRIPT>
        <h2>Search results for <i>X-Men The Animated Series</i></h2>
        </body></html>"""
        results = parse_search_results(html)
        assert len(results) == 1
        assert results[0].film_id == 23028
        assert results[0].title == "X-Men The Animated Series"
        assert "fid=23028" in results[0].url

    def test_js_redirect_not_used_when_links_present(self):
        html = """<html><body>
        <SCRIPT>location.href="film.php?fid=999";</SCRIPT>
        <a href="film.php?fid=100">Film A</a>
        </body></html>"""
        results = parse_search_results(html)
        assert len(results) == 1
        assert results[0].film_id == 100

    def test_no_results(self):
        html = """<html><body><h2>Search results</h2>
        Found 0 result(s).</body></html>"""
        results = parse_search_results(html)
        assert results == []
