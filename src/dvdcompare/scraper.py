from __future__ import annotations

import httpx

from .models import FilmComparison, SearchResult
from .parser import parse_film_page, parse_search_results

BASE_URL = "https://www.dvdcompare.net"

_HEADERS = {
    "User-Agent": "dvdcompare-scraper/0.1 (disc extras lookup)",
}


async def search(
    query: str, *, client: httpx.AsyncClient | None = None
) -> list[SearchResult]:
    """Search dvdcompare.net for a film title."""
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(headers=_HEADERS)
    try:
        resp = await client.post(
            f"{BASE_URL}/comparisons/search.php",
            data={"param": query, "searchtype": "text"},
            follow_redirects=True,
        )
        resp.raise_for_status()
        return parse_search_results(resp.text)
    finally:
        if own_client:
            await client.aclose()


async def find_film(
    title: str,
    disc_format: str | None = None,
    *,
    client: httpx.AsyncClient | None = None,
) -> FilmComparison:
    """Search for a title and return the best-matching FilmComparison.

    If *disc_format* is provided (e.g. ``"Blu-ray 4K"``), results whose
    title contains that format string are preferred.  Falls back to the
    first result when no format-specific match exists.

    Raises ``LookupError`` if no search results are found.
    """
    results = await search(title, client=client)
    if not results:
        raise LookupError(f"No dvdcompare results for '{title}'")

    best = results[0]
    if disc_format:
        fmt_lower = disc_format.lower()
        for r in results:
            if fmt_lower in r.title.lower():
                best = r
                break

    return await get_film(best.film_id, client=client)


async def get_film(
    film_id: int, *, client: httpx.AsyncClient | None = None
) -> FilmComparison:
    """Fetch and parse a film comparison page by dvdcompare film ID."""
    url = f"{BASE_URL}/comparisons/film.php?fid={film_id}"
    return await get_film_by_url(url, client=client)


async def get_film_by_url(
    url: str, *, client: httpx.AsyncClient | None = None
) -> FilmComparison:
    """Fetch and parse a film comparison page by full URL."""
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(headers=_HEADERS)
    try:
        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()
        return parse_film_page(resp.text)
    finally:
        if own_client:
            await client.aclose()
