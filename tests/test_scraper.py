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
        ),
        SearchResult(
            title="Oppenheimer (Blu-ray 4K)",
            url="https://www.dvdcompare.net/comparisons/film.php?fid=66397",
            film_id=66397,
        ),
        SearchResult(
            title="Oppenheimer (DVD)",
            url="https://www.dvdcompare.net/comparisons/film.php?fid=66399",
            film_id=66399,
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
