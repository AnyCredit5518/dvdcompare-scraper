from __future__ import annotations

import asyncio
import random

import httpx

from .models import FilmComparison, SearchResult
from .parser import parse_film_page, parse_search_results

BASE_URL = "https://www.dvdcompare.net"

_HEADERS = {
    "User-Agent": "dvdcompare-scraper/0.1 (disc extras lookup)",
}


_TIMEOUT = httpx.Timeout(15.0)  # 15s connect + read timeout


async def search(
    query: str, *, client: httpx.AsyncClient | None = None
) -> list[SearchResult]:
    """Search dvdcompare.net for a film title."""
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT)
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
    year: int | None = None,
    client: httpx.AsyncClient | None = None,
) -> FilmComparison:
    """Search for a title and return the best-matching FilmComparison.

    If *year* is provided, results matching that year are strongly
    preferred.  If *disc_format* is provided (e.g. ``"Blu-ray 4K"``),
    results whose title contains that format string are preferred.
    When both are given, year+format matches rank highest, then
    year-only, then format-only, then first result.

    Raises ``LookupError`` if no search results are found.
    """
    results = await search(title, client=client)
    if not results:
        raise LookupError(f"No dvdcompare results for '{title}'")

    fmt_lower = disc_format.lower() if disc_format else None

    def _score(r: SearchResult) -> int:
        s = 0
        if year and r.year == year:
            s += 2
        if fmt_lower and r.disc_format and fmt_lower == r.disc_format.lower():
            s += 1
        return s

    best = max(results, key=_score)
    await asyncio.sleep(2.0 + random.uniform(0, 1.0))  # rate-limit
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
        client = httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT)
    try:
        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()
        return parse_film_page(resp.content)
    finally:
        if own_client:
            await client.aclose()
