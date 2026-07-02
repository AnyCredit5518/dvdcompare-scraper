from unittest.mock import AsyncMock, patch

import pytest

from dvdcompare.models import Disc, Feature, FilmComparison, Release, SearchResult
from dvdcompare.scraper import _resolve_release_pointers, find_film, get_film


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



def _make_placeholder_disc(number, pointer_fid, title=""):
    return Disc(
        number=number,
        format="",
        title=title,
        pointer_fid=pointer_fid,
        pointer_url=f"film.php?fid={pointer_fid}",
    )


def _make_target_film(fid, num_discs, features_per_disc=1):
    """Build a FilmComparison whose first release has N discs, each with
    a placeholder feature so they are not treated as empty placeholders."""
    discs = []
    for i in range(num_discs):
        features = [
            Feature(title=f"Feature {i}-{j}", runtime_seconds=60)
            for j in range(features_per_disc)
        ]
        discs.append(Disc(number=i + 1, format="Blu-ray", features=features))
    return FilmComparison(
        title=f"Target {fid}",
        film_id=fid,
        releases=[Release(name=f"Release {fid}", discs=discs)],
    )


class TestResolveReleasePointers:
    @pytest.mark.asyncio
    async def test_range_pointers_replaced_by_target_discs(self):
        """Four placeholders pointing to fid=66231 are replaced by that
        release's four discs, renumbered to keep the outer sequence."""
        outer = Release(
            name="Complete Series",
            discs=[_make_placeholder_disc(n, 66231, "Season 1") for n in range(1, 5)],
        )
        target = _make_target_film(66231, num_discs=4)

        async def fake_get_film(fid, **kw):
            assert fid == 66231
            return target

        with patch("dvdcompare.scraper.get_film", new_callable=AsyncMock, side_effect=fake_get_film):
            await _resolve_release_pointers(outer, client=None, visited=set())

        assert len(outer.discs) == 4
        assert [d.number for d in outer.discs] == [1, 2, 3, 4]
        # Real features, not pointer placeholders
        assert all(d.features for d in outer.discs)
        assert all(d.pointer_fid is None for d in outer.discs)
        # Placeholder title propagated when target disc has no title
        assert all(d.title == "Season 1" for d in outer.discs)

    @pytest.mark.asyncio
    async def test_multiple_pointer_groups_and_real_disc(self):
        """Two pointer ranges + one rich disc: each range resolves, rich
        disc stays untouched, and outer numbering stays contiguous."""
        outer = Release(
            name="Complete Series",
            discs=[
                _make_placeholder_disc(1, 66231, "Season 1"),
                _make_placeholder_disc(2, 66231, "Season 1"),
                _make_placeholder_disc(3, 66232, "Season 2"),
                _make_placeholder_disc(4, 66232, "Season 2"),
                Disc(number=5, format="Blu-ray", is_film=True, features=[Feature(title="The Film")]),
            ],
        )
        s1 = _make_target_film(66231, num_discs=2)
        s2 = _make_target_film(66232, num_discs=2)

        async def fake_get_film(fid, **kw):
            return {66231: s1, 66232: s2}[fid]

        with patch("dvdcompare.scraper.get_film", new_callable=AsyncMock, side_effect=fake_get_film):
            await _resolve_release_pointers(outer, client=None, visited=set())

        assert [d.number for d in outer.discs] == [1, 2, 3, 4, 5]
        assert outer.discs[4].is_film is True
        assert outer.discs[4].features[0].title == "The Film"
        assert all(d.pointer_fid is None for d in outer.discs)

    @pytest.mark.asyncio
    async def test_pointer_failure_leaves_placeholders(self):
        """Network / parse errors from get_film must not blow up — the
        placeholders are left in place instead."""
        outer = Release(
            name="Complete Series",
            discs=[
                _make_placeholder_disc(1, 66231, "Season 1"),
                _make_placeholder_disc(2, 66231, "Season 1"),
            ],
        )

        async def fake_get_film(fid, **kw):
            raise RuntimeError("network down")

        with patch("dvdcompare.scraper.get_film", new_callable=AsyncMock, side_effect=fake_get_film):
            await _resolve_release_pointers(outer, client=None, visited=set())

        assert len(outer.discs) == 2
        assert all(d.pointer_fid == 66231 for d in outer.discs)

    @pytest.mark.asyncio
    async def test_cycle_detection(self):
        """If a target fid is already in ``visited``, its placeholders are
        left alone (no infinite recursion)."""
        outer = Release(
            name="Complete Series",
            discs=[_make_placeholder_disc(1, 66231, "Season 1")],
        )

        async def fake_get_film(fid, **kw):
            pytest.fail("get_film should not be called for cycle target")

        with patch("dvdcompare.scraper.get_film", new_callable=AsyncMock, side_effect=fake_get_film):
            await _resolve_release_pointers(outer, client=None, visited={66231})

        assert len(outer.discs) == 1
        assert outer.discs[0].pointer_fid == 66231

    @pytest.mark.asyncio
    async def test_get_film_resolve_pointers_flag_default_off(self):
        """``get_film`` without ``resolve_pointers`` keeps placeholders."""
        from dvdcompare.scraper import get_film_by_url

        placeholder_film = FilmComparison(
            title="Psych: The Movie",
            film_id=66239,
            releases=[
                Release(
                    name="Complete Series",
                    discs=[_make_placeholder_disc(1, 66231, "Season 1")],
                )
            ],
        )

        class FakeResp:
            content = b""
            def raise_for_status(self):
                pass

        class FakeClient:
            async def get(self, url, **kw):
                return FakeResp()
            async def aclose(self):
                pass

        with patch("dvdcompare.scraper.parse_film_page", return_value=placeholder_film):
            film = await get_film_by_url(
                "http://example/film.php?fid=66239",
                client=FakeClient(),
            )

        assert film.releases[0].discs[0].pointer_fid == 66231

    @pytest.mark.asyncio
    async def test_target_release_placeholder_discs_are_dropped(self):
        """Season pages typically re-list the whole box (e.g. Season 1's page
        has 4 real Season 1 discs plus placeholder pointers for Seasons 2-8).
        Only the concrete discs should be spliced in; the nested placeholders
        must be dropped to avoid multiplying the outer disc count.
        """
        # Outer: 4 placeholders for Season 1 + 4 for Season 2.
        outer = Release(
            name="Complete Series",
            discs=[
                _make_placeholder_disc(1, 66231, "Season 1"),
                _make_placeholder_disc(2, 66231, "Season 1"),
                _make_placeholder_disc(3, 66231, "Season 1"),
                _make_placeholder_disc(4, 66231, "Season 1"),
                _make_placeholder_disc(5, 66232, "Season 2"),
                _make_placeholder_disc(6, 66232, "Season 2"),
                _make_placeholder_disc(7, 66232, "Season 2"),
                _make_placeholder_disc(8, 66232, "Season 2"),
            ],
        )
        # Season 1 target: 4 concrete Season 1 discs, then 4 pointer
        # placeholders for Season 2 (this mirrors the real dvdcompare page).
        season1 = FilmComparison(
            title="Psych: Season 1",
            film_id=66231,
            releases=[
                Release(
                    name="Complete Series",
                    discs=[
                        Disc(number=1, format="Blu-ray", features=[Feature(title="S1D1")]),
                        Disc(number=2, format="Blu-ray", features=[Feature(title="S1D2")]),
                        Disc(number=3, format="Blu-ray", features=[Feature(title="S1D3")]),
                        Disc(number=4, format="Blu-ray", features=[Feature(title="S1D4")]),
                        _make_placeholder_disc(5, 66232, "Season 2"),
                        _make_placeholder_disc(6, 66232, "Season 2"),
                        _make_placeholder_disc(7, 66232, "Season 2"),
                        _make_placeholder_disc(8, 66232, "Season 2"),
                    ],
                )
            ],
        )
        # Season 2 target: same shape.
        season2 = FilmComparison(
            title="Psych: Season 2",
            film_id=66232,
            releases=[
                Release(
                    name="Complete Series",
                    discs=[
                        _make_placeholder_disc(1, 66231, "Season 1"),
                        _make_placeholder_disc(2, 66231, "Season 1"),
                        _make_placeholder_disc(3, 66231, "Season 1"),
                        _make_placeholder_disc(4, 66231, "Season 1"),
                        Disc(number=5, format="Blu-ray", features=[Feature(title="S2D1")]),
                        Disc(number=6, format="Blu-ray", features=[Feature(title="S2D2")]),
                        Disc(number=7, format="Blu-ray", features=[Feature(title="S2D3")]),
                        Disc(number=8, format="Blu-ray", features=[Feature(title="S2D4")]),
                    ],
                )
            ],
        )

        async def fake_get_film(fid, **kw):
            return {66231: season1, 66232: season2}[fid]

        with patch("dvdcompare.scraper.get_film", new_callable=AsyncMock, side_effect=fake_get_film):
            await _resolve_release_pointers(outer, client=None, visited=set())

        # Result: 8 concrete discs, not 8 + 4 + 4 = 16, and not 8 * 2 = 16.
        assert len(outer.discs) == 8
        assert [d.number for d in outer.discs] == [1, 2, 3, 4, 5, 6, 7, 8]
        assert all(d.pointer_fid is None for d in outer.discs)
        titles = [d.features[0].title for d in outer.discs]
        assert titles == ["S1D1", "S1D2", "S1D3", "S1D4", "S2D1", "S2D2", "S2D3", "S2D4"]

    @pytest.mark.asyncio
    async def test_target_with_only_placeholders_leaves_outer_placeholders(self):
        """If the target release is nothing but placeholders (nothing
        concrete to splice), the outer placeholders are preserved so the
        caller still sees the disc slots."""
        outer = Release(
            name="Complete Series",
            discs=[
                _make_placeholder_disc(1, 66231, "Season 1"),
                _make_placeholder_disc(2, 66231, "Season 1"),
            ],
        )
        # Target only re-lists other seasons as placeholders — no real discs.
        empty_target = FilmComparison(
            title="Empty",
            film_id=66231,
            releases=[
                Release(
                    name="Complete Series",
                    discs=[
                        _make_placeholder_disc(1, 66232, "Season 2"),
                        _make_placeholder_disc(2, 66233, "Season 3"),
                    ],
                )
            ],
        )

        async def fake_get_film(fid, **kw):
            return empty_target

        with patch("dvdcompare.scraper.get_film", new_callable=AsyncMock, side_effect=fake_get_film):
            await _resolve_release_pointers(outer, client=None, visited=set())

        assert len(outer.discs) == 2
        assert all(d.pointer_fid == 66231 for d in outer.discs)


    @pytest.mark.asyncio
    async def test_target_release_truncated_to_placeholder_count(self):
        """When the season page ships more discs than the outer range
        allocates (e.g. standalone boxset has 5 discs but the Complete
        Series slots 4), only the first N discs are spliced in so the
        outer numbering stays intact."""
        outer = Release(
            name="Complete Series",
            discs=[_make_placeholder_disc(n, 66231, "Season 1") for n in range(1, 5)],
        )
        # Target has 5 real discs but outer only has 4 placeholder slots.
        big_target = FilmComparison(
            title="Season 1 Standalone",
            film_id=66231,
            releases=[
                Release(
                    name="C",
                    discs=[
                        Disc(number=1, format="BD", features=[Feature(title=f"D{n}")])
                        for n in range(1, 6)
                    ],
                )
            ],
        )

        async def fake_get_film(fid, **kw):
            return big_target

        with patch("dvdcompare.scraper.get_film", new_callable=AsyncMock, side_effect=fake_get_film):
            await _resolve_release_pointers(outer, client=None, visited=set())

        assert [d.number for d in outer.discs] == [1, 2, 3, 4]
        assert [d.features[0].title for d in outer.discs] == ["D1", "D2", "D3", "D4"]
