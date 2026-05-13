from __future__ import annotations

import asyncio
import os
import random

import httpx

from .models import FilmComparison, SearchResult
from .parser import parse_film_page, parse_search_results

BASE_URL = "https://www.dvdcompare.net"

# Use a real browser User-Agent and browser-typical headers so the scraper
# doesn't trivially identify itself as a bot. The default UA used to literally
# include the word "scraper", which made simple log-grep blocks possible.
# Override via the DVDCOMPARE_USER_AGENT environment variable.
_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) "
    "Gecko/20100101 Firefox/124.0"
)


def _build_headers(*, referer: str | None = None) -> dict[str, str]:
    """Construct browser-like request headers."""
    headers = {
        "User-Agent": os.environ.get("DVDCOMPARE_USER_AGENT", _DEFAULT_USER_AGENT),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
    }
    if referer:
        headers["Referer"] = referer
    return headers


_TIMEOUT = httpx.Timeout(15.0)  # 15s connect + read timeout


def _new_client() -> httpx.AsyncClient:
    """Create a default async client with browser headers + cookie jar."""
    return httpx.AsyncClient(
        headers=_build_headers(),
        timeout=_TIMEOUT,
        follow_redirects=True,
    )


async def search(
    query: str, *, client: httpx.AsyncClient | None = None
) -> list[SearchResult]:
    """Search dvdcompare.net for a film title."""
    own_client = client is None
    if own_client:
        client = _new_client()
    try:
        resp = await client.post(
            f"{BASE_URL}/comparisons/search.php",
            data={"param": query, "searchtype": "text"},
            headers={"Referer": f"{BASE_URL}/"},
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

    Internally reuses a single ``httpx.AsyncClient`` across the search and
    the film-page fetch so cookies persist and the connection is reused,
    matching real browser behavior.

    Raises ``LookupError`` if no search results are found.
    """
    own_client = client is None
    if own_client:
        client = _new_client()
    try:
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
        await asyncio.sleep(2.0 + random.uniform(0, 1.0))  # human-like pause
        # Real browsers arrive at a film page via the search results, so
        # advertise that referer for the second request.
        referer = f"{BASE_URL}/comparisons/search.php"
        return await get_film(best.film_id, client=client, referer=referer)
    finally:
        if own_client:
            await client.aclose()


async def get_film(
    film_id: int,
    *,
    client: httpx.AsyncClient | None = None,
    referer: str | None = None,
) -> FilmComparison:
    """Fetch and parse a film comparison page by dvdcompare film ID."""
    url = f"{BASE_URL}/comparisons/film.php?fid={film_id}"
    return await get_film_by_url(url, client=client, referer=referer)


async def get_film_by_url(
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
    referer: str | None = None,
) -> FilmComparison:
    """Fetch and parse a film comparison page by full URL."""
    own_client = client is None
    if own_client:
        client = _new_client()
    try:
        headers = {"Referer": referer} if referer else None
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return parse_film_page(resp.content)
    finally:
        if own_client:
            await client.aclose()
