from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Feature:
    """A single bonus feature on a disc."""

    title: str
    runtime_seconds: int | None = None
    feature_type: str | None = None
    year: int | None = None
    technical_notes: str | None = None
    is_play_all: bool = False
    children: list[Feature] = field(default_factory=list)


@dataclass
class Disc:
    """A single disc in a release."""

    number: int
    format: str
    is_film: bool = False
    features: list[Feature] = field(default_factory=list)


@dataclass
class Release:
    """A regional release of a film."""

    name: str
    year: int | None = None
    discs: list[Disc] = field(default_factory=list)


@dataclass
class FilmComparison:
    """A complete film comparison page from dvdcompare.net."""

    title: str
    year: int | None = None
    format: str | None = None
    director: str | None = None
    imdb_url: str | None = None
    imdb_id: str | None = None
    film_id: int | None = None
    releases: list[Release] = field(default_factory=list)


@dataclass
class SearchResult:
    """A single result from a dvdcompare.net search."""

    title: str
    url: str
    film_id: int | None = None
