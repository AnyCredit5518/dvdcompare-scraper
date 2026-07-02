from __future__ import annotations

import asyncio
import os
import random

import httpx

from .models import FilmComparison, Release, SearchResult
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


# Public alias for callers (e.g. status pings) that need to reuse the same
# headers without importing the underscore-prefixed name.
build_browser_headers = _build_headers


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
    resolve_pointers: bool = False,
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
        return await get_film(
            best.film_id,
            client=client,
            referer=referer,
            resolve_pointers=resolve_pointers,
        )
    finally:
        if own_client:
            await client.aclose()


async def get_film(
    film_id: int,
    *,
    client: httpx.AsyncClient | None = None,
    referer: str | None = None,
    resolve_pointers: bool = False,
) -> FilmComparison:
    """Fetch and parse a film comparison page by dvdcompare film ID.

    When ``resolve_pointers`` is ``True``, box-set placeholder discs that
    link to another film page (e.g. ``DISCS ONE - FOUR: Season 1``) are
    followed and the returned page's discs are spliced in place of the
    placeholders.
    """
    url = f"{BASE_URL}/comparisons/film.php?fid={film_id}"
    return await get_film_by_url(
        url,
        client=client,
        referer=referer,
        resolve_pointers=resolve_pointers,
    )


async def get_film_by_url(
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
    referer: str | None = None,
    resolve_pointers: bool = False,
) -> FilmComparison:
    """Fetch and parse a film comparison page by full URL.

    See :func:`get_film` for ``resolve_pointers``.
    """
    own_client = client is None
    if own_client:
        client = _new_client()
    try:
        headers = {"Referer": referer} if referer else None
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        film = parse_film_page(resp.content)
        if resolve_pointers:
            visited: set[int] = set()
            if film.film_id is not None:
                visited.add(film.film_id)
            for release in film.releases:
                await _resolve_release_pointers(
                    release,
                    client=client,
                    visited=visited,
                    referer=url,
                )
        return film
    finally:
        if own_client:
            await client.aclose()


async def _resolve_release_pointers(
    release: "Release",
    *,
    client: httpx.AsyncClient,
    visited: set[int],
    referer: str | None = None,
) -> None:
    """Replace pointer-only placeholder discs in ``release`` with the discs
    from the film pages they link to.

    Consecutive placeholders sharing the same ``pointer_fid`` are grouped
    and replaced together with the target release's discs. Discs that
    already have features, that lack a pointer, or whose pointer would
    cause a cycle are left untouched.
    """
    new_discs = []
    i = 0
    while i < len(release.discs):
        d = release.discs[i]
        should_follow = (
            d.pointer_fid is not None
            and not d.features
            and d.pointer_fid not in visited
        )
        if not should_follow:
            new_discs.append(d)
            i += 1
            continue

        # Group consecutive discs pointing to the same fid.
        target_fid = d.pointer_fid
        j = i
        while (
            j < len(release.discs)
            and release.discs[j].pointer_fid == target_fid
            and not release.discs[j].features
        ):
            j += 1
        placeholders = release.discs[i:j]

        try:
            target = await get_film(
                target_fid,
                client=client,
                referer=referer,
                resolve_pointers=False,
            )
        except Exception:
            # Network / parse failure — leave placeholders in place so the
            # caller still sees the disc structure derived from the top
            # page. This is deliberately permissive: pointer resolution is
            # best-effort.
            new_discs.extend(placeholders)
            i = j
            continue

        visited.add(target_fid)
        target_release = _pick_matching_release(target, release)
        if target_release is None or not target_release.discs:
            new_discs.extend(placeholders)
            i = j
            continue

        # Season pages typically re-list the whole box (e.g. Season 1's page
        # has 4 real Season 1 discs plus placeholder pointers for Seasons
        # 2-8). Keep only concrete discs — placeholders would blow up the
        # outer disc count on every season and their content is already
        # reached via the outer release's own placeholders.
        target_discs = [td for td in target_release.discs if td.pointer_fid is None]
        if not target_discs:
            new_discs.extend(placeholders)
            i = j
            continue

        # The season page's release may still carry more discs than the outer
        # range slot allocates (a standalone boxset often ships an extra
        # bonus disc that the Complete Series consolidates away). Trim to
        # the placeholder range so the outer disc numbering stays correct.
        target_discs = target_discs[: len(placeholders)]

        # Renumber the target discs to match the placeholder positions so
        # downstream consumers see contiguous disc numbers on the outer
        # release.
        base_num = placeholders[0].number or (len(new_discs) + 1)
        for k, td in enumerate(target_discs):
            td.number = base_num + k
            # Preserve the placeholder's label (e.g. "Season 1") when the
            # target disc has no title of its own.
            if not td.title and placeholders and placeholders[0].title:
                td.title = placeholders[0].title
            new_discs.append(td)
        i = j

    release.discs = new_discs


def _pick_matching_release(
    target: FilmComparison, outer: "Release"
) -> "Release | None":
    """Choose the release on ``target`` that best matches ``outer``.

    Prefers a release with the same year; falls back to the first
    release. Returns ``None`` when the target has no releases.
    """
    if not target.releases:
        return None
    if outer.year:
        for r in target.releases:
            if r.year == outer.year:
                return r
    return target.releases[0]
