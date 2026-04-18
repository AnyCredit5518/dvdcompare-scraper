from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict

from .models import Release
from .parser import format_runtime
from .scraper import get_film, get_film_by_url, search


def select_releases(releases: list[Release], selector: str) -> list[Release]:
    """Filter releases by 1-based index or case-insensitive name substring."""
    try:
        idx = int(selector) - 1
        idx = min(idx, len(releases) - 1)
        return [releases[idx]]
    except ValueError:
        pass

    keyword = selector.lower()
    matched = [r for r in releases if keyword in r.name.lower()]
    if matched:
        return matched

    print("No release matching '{}'.".format(selector), file=sys.stderr)
    print("Available releases:", file=sys.stderr)
    for i, r in enumerate(releases, 1):
        print(f"  {i}. {r.name}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape disc extras metadata from dvdcompare.net",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("query", nargs="?", help="Search query (film title)")
    group.add_argument("--id", type=int, dest="film_id", help="dvdcompare film ID")
    group.add_argument("--url", help="dvdcompare film page URL")

    parser.add_argument(
        "--release",
        default="1",
        help="Release number (1-based) or name keyword (default: 1)",
    )
    parser.add_argument(
        "--all-releases",
        action="store_true",
        help="Show all releases instead of just one",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()
    asyncio.run(_run(args))


async def _run(args: argparse.Namespace) -> None:
    if args.film_id:
        film = await get_film(args.film_id)
    elif args.url:
        film = await get_film_by_url(args.url)
    else:
        results = await search(args.query)
        if not results:
            print("No results found.", file=sys.stderr)
            sys.exit(1)
        if len(results) > 1:
            print(f"Found {len(results)} results:", file=sys.stderr)
            for i, r in enumerate(results, 1):
                print(f"  {i}. {r.title} (fid={r.film_id})", file=sys.stderr)
            print(
                "Using first result. Use --id to select a specific one.",
                file=sys.stderr,
            )
        film = await get_film(results[0].film_id)

    if not args.all_releases and film.releases:
        film.releases = select_releases(film.releases, args.release)

    if args.json:
        print(json.dumps(asdict(film), indent=2))
    else:
        _print_text(film, args)


def _print_text(film, args: argparse.Namespace) -> None:
    header = film.title
    if film.format:
        header += f" ({film.format})"
    if film.year:
        header += f" ({film.year})"
    print(header)
    if film.director:
        print(f"Director: {film.director}")
    if film.imdb_id:
        print(f"IMDB: {film.imdb_id}")
    print()

    for release in film.releases:
        line = f"--- {release.name}"
        if release.year:
            line += f" [{release.year}]"
        line += " ---"
        print(line)

        for disc in release.discs:
            print(f"\n  DISC {disc.number} ({disc.format})")
            if disc.is_film:
                print("    The Film")
            for feature in disc.features:
                _print_feature(feature, indent=4)
        print()


def _print_feature(feature, indent: int = 4) -> None:
    prefix = " " * indent
    parts = [f'{prefix}"{feature.title}"']
    if feature.year:
        parts.append(str(feature.year))
    if feature.feature_type:
        parts.append(feature.feature_type)
    if feature.runtime_seconds is not None:
        rt = format_runtime(feature.runtime_seconds)
        if feature.is_play_all:
            parts.append(f"(Play All - {rt})")
        else:
            parts.append(f"({rt})")
    if feature.technical_notes:
        parts.append(f"[{feature.technical_notes}]")
    print(" ".join(parts))

    for child in feature.children:
        _print_feature(child, indent=indent + 2)
