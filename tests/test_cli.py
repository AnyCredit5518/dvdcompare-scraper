import pytest

from dvdcompare.cli import select_releases
from dvdcompare.models import Release


@pytest.fixture
def releases():
    return [
        Release(name="Blu-ray ALL America - BBC", year=2024),
        Release(name="Blu-ray ALL United Kingdom - BBC", year=2024),
    ]


class TestSelectReleases:
    def test_index_one(self, releases):
        result = select_releases(releases, "1")
        assert len(result) == 1
        assert "America" in result[0].name

    def test_index_two(self, releases):
        result = select_releases(releases, "2")
        assert len(result) == 1
        assert "United Kingdom" in result[0].name

    def test_index_out_of_range_clamps(self, releases):
        result = select_releases(releases, "99")
        assert len(result) == 1
        assert "United Kingdom" in result[0].name

    def test_keyword_america(self, releases):
        result = select_releases(releases, "america")
        assert len(result) == 1
        assert "America" in result[0].name

    def test_keyword_kingdom(self, releases):
        result = select_releases(releases, "kingdom")
        assert len(result) == 1
        assert "United Kingdom" in result[0].name

    def test_keyword_case_insensitive(self, releases):
        result = select_releases(releases, "AMERICA")
        assert len(result) == 1
        assert "America" in result[0].name

    def test_keyword_bbc_matches_both(self, releases):
        result = select_releases(releases, "bbc")
        assert len(result) == 2

    def test_keyword_no_match_exits(self, releases):
        with pytest.raises(SystemExit) as exc_info:
            select_releases(releases, "nonexistent")
        assert exc_info.value.code == 1
