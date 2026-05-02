from unittest.mock import AsyncMock, patch

import pytest

from dvdcompare.models import FilmComparison, SearchResult
from dvdcompare.scraper import find_film


@pytest.fixture
def search_results():
    return [
        SearchResult(
            title="Oppenheimer (Blu-ray)",
            url="https://www.dvdcompare.net/comparisons/film.php?fid=66398",
            film_id=66398,
            disc_format="Blu-ray",
        ),
        SearchResult(
            title="Oppenheimer (Blu-ray 4K)",
            url="https://www.dvdcompare.net/comparisons/film.php?fid=66397",
            film_id=66397,
            disc_format="Blu-ray 4K",
        ),
        SearchResult(
            title="Oppenheimer (DVD)",
            url="https://www.dvdcompare.net/comparisons/film.php?fid=66399",
            film_id=66399,
            disc_format="DVD",
        ),
    ]


def _fake_film(film_id):
    return FilmComparison(title="Oppenheimer", film_id=film_id)


class TestFindFilm:
    @pytest.mark.asyncio
    async def test_no_results_raises(self):
        with patch("dvdcompare.scraper.search", new_callable=AsyncMock, return_value=[]):
            with pytest.raises(LookupError, match="No dvdcompare results"):
                await find_film("Nonexistent Movie")

    @pytest.mark.asyncio
    async def test_no_format_returns_first(self, search_results):
        with (
            patch("dvdcompare.scraper.search", new_callable=AsyncMock, return_value=search_results),
            patch("dvdcompare.scraper.get_film", new_callable=AsyncMock, side_effect=lambda fid, **kw: _fake_film(fid)),
        ):
            result = await find_film("Oppenheimer")
            assert result.film_id == 66398  # first result

    @pytest.mark.asyncio
    async def test_format_filter_selects_4k(self, search_results):
        with (
            patch("dvdcompare.scraper.search", new_callable=AsyncMock, return_value=search_results),
            patch("dvdcompare.scraper.get_film", new_callable=AsyncMock, side_effect=lambda fid, **kw: _fake_film(fid)),
        ):
            result = await find_film("Oppenheimer", "Blu-ray 4K")
            assert result.film_id == 66397

    @pytest.mark.asyncio
    async def test_format_filter_selects_dvd(self, search_results):
        with (
            patch("dvdcompare.scraper.search", new_callable=AsyncMock, return_value=search_results),
            patch("dvdcompare.scraper.get_film", new_callable=AsyncMock, side_effect=lambda fid, **kw: _fake_film(fid)),
        ):
            result = await find_film("Oppenheimer", "DVD")
            assert result.film_id == 66399

    @pytest.mark.asyncio
    async def test_format_filter_case_insensitive(self, search_results):
        with (
            patch("dvdcompare.scraper.search", new_callable=AsyncMock, return_value=search_results),
            patch("dvdcompare.scraper.get_film", new_callable=AsyncMock, side_effect=lambda fid, **kw: _fake_film(fid)),
        ):
            result = await find_film("Oppenheimer", "blu-ray 4k")
            assert result.film_id == 66397

    @pytest.mark.asyncio
    async def test_format_no_match_falls_back_to_first(self, search_results):
        with (
            patch("dvdcompare.scraper.search", new_callable=AsyncMock, return_value=search_results),
            patch("dvdcompare.scraper.get_film", new_callable=AsyncMock, side_effect=lambda fid, **kw: _fake_film(fid)),
        ):
            result = await find_film("Oppenheimer", "HD-DVD")
            assert result.film_id == 66398  # falls back to first


# --- Year-aware selection (King Kong scenario) ---

@pytest.fixture
def king_kong_results():
    """Multiple King Kong entries spanning different years and formats."""
    return [
        SearchResult(title="King Kong                         (1976)", url="...", film_id=2451, year=1976),
        SearchResult(title="King Kong                         (1933)", url="...", film_id=2930, year=1933),
        SearchResult(title="King Kong                         (2005)", url="...", film_id=8522, year=2005),
        SearchResult(title="King Kong (Blu-ray 4K)                           (1976)", url="...", film_id=62974, year=1976, disc_format="Blu-ray 4K"),
        SearchResult(title="King Kong (Blu-ray 4K)                           (2005)", url="...", film_id=42946, year=2005, disc_format="Blu-ray 4K"),
        SearchResult(title="King Kong (Blu-ray)                              (2005)", url="...", film_id=13977, year=2005, disc_format="Blu-ray"),
        SearchResult(title="King Kong (Blu-ray)                              (1933)", url="...", film_id=17828, year=1933, disc_format="Blu-ray"),
        SearchResult(title="King Kong (Blu-ray)                              (1976)", url="...", film_id=18539, year=1976, disc_format="Blu-ray"),
    ]


class TestFindFilmYear:
    @pytest.mark.asyncio
    async def test_year_and_format_selects_correct_entry(self, king_kong_results):
        """King Kong 2005 Blu-ray 4K should pick film_id 42946, not 1976."""
        with (
            patch("dvdcompare.scraper.search", new_callable=AsyncMock, return_value=king_kong_results),
            patch("dvdcompare.scraper.get_film", new_callable=AsyncMock, side_effect=lambda fid, **kw: _fake_film(fid)),
        ):
            result = await find_film("King Kong", "Blu-ray 4K", year=2005)
            assert result.film_id == 42946

    @pytest.mark.asyncio
    async def test_year_only_prefers_year_match(self, king_kong_results):
        with (
            patch("dvdcompare.scraper.search", new_callable=AsyncMock, return_value=king_kong_results),
            patch("dvdcompare.scraper.get_film", new_callable=AsyncMock, side_effect=lambda fid, **kw: _fake_film(fid)),
        ):
            result = await find_film("King Kong", year=2005)
            # Should pick one of the 2005 entries (first 2005 by order = 8522)
            assert result.film_id in (8522, 42946, 13977)

    @pytest.mark.asyncio
    async def test_format_only_without_year_picks_first_format_match(self, king_kong_results):
        """Without year, Blu-ray 4K picks the first format match (1976)."""
        with (
            patch("dvdcompare.scraper.search", new_callable=AsyncMock, return_value=king_kong_results),
            patch("dvdcompare.scraper.get_film", new_callable=AsyncMock, side_effect=lambda fid, **kw: _fake_film(fid)),
        ):
            result = await find_film("King Kong", "Blu-ray 4K")
            assert result.film_id == 62974  # 1976 4K — first format match

    @pytest.mark.asyncio
    async def test_year_beats_format_when_no_combined_match(self):
        """Year match should outrank format-only match."""
        results = [
            SearchResult(title="Foo (Blu-ray 4K)  (1990)", url="...", film_id=1, year=1990, disc_format="Blu-ray 4K"),
            SearchResult(title="Foo               (2020)", url="...", film_id=2, year=2020),
        ]
        with (
            patch("dvdcompare.scraper.search", new_callable=AsyncMock, return_value=results),
            patch("dvdcompare.scraper.get_film", new_callable=AsyncMock, side_effect=lambda fid, **kw: _fake_film(fid)),
        ):
            result = await find_film("Foo", "Blu-ray 4K", year=2020)
            assert result.film_id == 2  # year match wins over format match

    @pytest.mark.asyncio
    async def test_no_year_no_format_returns_first(self, king_kong_results):
        with (
            patch("dvdcompare.scraper.search", new_callable=AsyncMock, return_value=king_kong_results),
            patch("dvdcompare.scraper.get_film", new_callable=AsyncMock, side_effect=lambda fid, **kw: _fake_film(fid)),
        ):
            result = await find_film("King Kong")
            assert result.film_id == 2451  # first in list
