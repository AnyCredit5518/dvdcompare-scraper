from __future__ import annotations

import html as html_module
import re

from bs4 import BeautifulSoup

from .models import Disc, Feature, FilmComparison, Release, SearchResult

_DISC_WORDS = {
    "ONE": 1,
    "TWO": 2,
    "THREE": 3,
    "FOUR": 4,
    "FIVE": 5,
    "SIX": 6,
    "SEVEN": 7,
    "EIGHT": 8,
    "NINE": 9,
    "TEN": 10,
}


def parse_runtime(s: str) -> int:
    """Parse ``MM:SS``, ``H:MM:SS``, or ``NNN mins`` into total seconds."""
    s = s.strip()
    mins_match = re.match(r"^(\d+)\s*mins?$", s)
    if mins_match:
        return int(mins_match.group(1)) * 60
    parts = s.split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return 0


def format_runtime(seconds: int) -> str:
    """Format total seconds as ``MM:SS`` or ``H:MM:SS``."""
    mins, secs = divmod(seconds, 60)
    hours, mins = divmod(mins, 60)
    if hours:
        return f"{hours}:{mins:02d}:{secs:02d}"
    return f"{mins}:{secs:02d}"


def _disc_number(word: str) -> int:
    word = word.upper()
    if word in _DISC_WORDS:
        return _DISC_WORDS[word]
    try:
        return int(word)
    except ValueError:
        return 0


def parse_feature_line(line: str) -> Feature:
    """Parse a single feature text line into a :class:`Feature`."""
    technical_notes = None
    is_play_all = False
    runtime_seconds = None
    year = None
    feature_type = None

    # 1. Extract technical notes [...]
    tech_match = re.search(r"\s*\[([^\]]+)\]", line)
    if tech_match:
        technical_notes = tech_match.group(1)
        line = line[: tech_match.start()] + line[tech_match.end() :]

    # 2. Strip trailing colon (group indicator) -- detected by caller
    line = line.strip()
    if line.endswith(":"):
        line = line[:-1].strip()

    # 3. Extract runtime  (MM:SS) / (H:MM:SS) / (Play All - MM:SS) / (NNN mins)
    #    Also handles "with Play All option - MM:SS"
    runtime_match = re.search(
        r"\((?:(?:with )?(Play All)(?: option)? - )?(\d{1,3}:\d{2}(?::\d{2})?|\d+\s*mins?)\)",
        line,
    )
    if runtime_match:
        if runtime_match.group(1):
            is_play_all = True
        runtime_seconds = parse_runtime(runtime_match.group(2))
        line = line[: runtime_match.start()] + line[runtime_match.end() :]
        line = line.strip()

    # 3b. Strip trailing colon again (may be exposed after runtime removal)
    if line.endswith(":"):
        line = line[:-1].strip()

    # 4. Extract quoted title vs unquoted
    quote_match = re.match(r'^["\u201c](.+?)["\u201d](.*)$', line)
    if quote_match:
        title = quote_match.group(1).strip()
        rest = quote_match.group(2).strip()
    else:
        title = line.strip()
        rest = ""

    # 5. From rest, extract year and type
    if rest:
        year_match = re.match(r"^(\d{4})\s*(.*)", rest)
        if year_match:
            year = int(year_match.group(1))
            feature_type = year_match.group(2).strip() or None
        else:
            feature_type = rest.strip() or None

    # Normalize whitespace in title
    title = re.sub(r"\s+", " ", title).strip()

    return Feature(
        title=title,
        runtime_seconds=runtime_seconds,
        feature_type=feature_type,
        year=year,
        technical_notes=technical_notes,
        is_play_all=is_play_all,
    )


def parse_extras(extras_html: str) -> list[Disc]:
    """Parse the inner HTML of an extras description div into :class:`Disc` objects."""
    # Replace <br> variants with newlines
    text = re.sub(r"<br\s*/?>", "\n", extras_html)
    # Remove all remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Decode HTML entities
    text = html_module.unescape(text)

    lines = [ln.strip() for ln in text.split("\n")]

    discs: list[Disc] = []
    current_disc: Disc | None = None
    current_group: Feature | None = None

    for line in lines:
        if not line:
            continue

        # Disc header: DISC ONE (Blu-ray 4K)
        disc_match = re.match(r"^DISC\s+(\w+)\s+\((.+)\)$", line)
        if disc_match:
            current_disc = Disc(
                number=_disc_number(disc_match.group(1)),
                format=disc_match.group(2),
            )
            discs.append(current_disc)
            current_group = None
            continue

        # "* The Film" marker
        if line == "* The Film":
            if current_disc:
                current_disc.is_film = True
            continue

        if current_disc is None:
            continue

        # Sub-feature (starts with "- ")
        if line.startswith("- "):
            feature = parse_feature_line(line[2:])
            if current_group:
                current_group.children.append(feature)
            else:
                current_disc.features.append(feature)
            continue

        feature = parse_feature_line(line)
        current_disc.features.append(feature)

        # Detect group header (trailing colon or play-all)
        is_group = line.rstrip().endswith(":") or feature.is_play_all

        if is_group:
            current_group = feature
        else:
            current_group = None

    return discs


def parse_film_page(html: str) -> FilmComparison:
    """Parse a dvdcompare.net film comparison page into a :class:`FilmComparison`."""
    soup = BeautifulSoup(html, "html.parser")

    # --- Title, format, year from <h2> ---
    title = ""
    year = None
    disc_format = None
    h2 = soup.find("h2")
    if h2:
        h2_text = h2.get_text(strip=True)
        # Last (YYYY) is the year
        year_match = re.search(r"\((\d{4})\)\s*$", h2_text)
        if year_match:
            year = int(year_match.group(1))
            rest = h2_text[: year_match.start()].strip()
        else:
            rest = h2_text
        # Format in parens at end of remainder
        fmt_match = re.search(r"\(([^)]+)\)\s*$", rest)
        if fmt_match:
            disc_format = fmt_match.group(1)
            title = rest[: fmt_match.start()].strip()
        else:
            title = rest

    # --- IMDB ---
    imdb_url = None
    imdb_id = None
    imdb_link = soup.find("a", href=re.compile(r"imdb\.com/title/"))
    if imdb_link:
        imdb_url = imdb_link["href"]
        id_match = re.search(r"/(tt\d+)", imdb_url)
        if id_match:
            imdb_id = id_match.group(1)

    # --- Director ---
    director = None
    content_div = soup.find("div", id="content")
    if content_div:
        dir_match = re.search(
            r"Director:\s*(.+?)(?:\n|$)", content_div.get_text()
        )
        if dir_match:
            director = dir_match.group(1).strip()

    # --- Film ID ---
    film_id = None
    form = soup.find("form", action=re.compile(r"film\.php\?fid="))
    if form:
        fid_match = re.search(r"fid=(\d+)", form["action"])
        if fid_match:
            film_id = int(fid_match.group(1))

    # --- Releases ---
    releases: list[Release] = []
    table = soup.find("table", attrs={"border": "0", "align": "center"})
    if table:
        for tr in table.find_all("tr"):
            ul = tr.find("ul", class_="dvd")
            if not ul:
                continue

            h3 = ul.find("h3")
            if not h3:
                continue

            # Release name and year
            release_year = None
            year_span = h3.find("span", class_="disc-release-year")
            if year_span:
                ry_match = re.search(r"\[(\d{4})", year_span.get_text())
                if ry_match:
                    release_year = int(ry_match.group(1))
                release_name = h3.get_text(strip=True).replace(
                    year_span.get_text(strip=True), ""
                ).strip()
            else:
                release_name = h3.get_text(strip=True)

            # Find extras
            discs: list[Disc] = []
            for li in ul.find_all("li", recursive=False):
                label_div = li.find("div", class_="label")
                if label_div and "Extras:" in label_div.get_text():
                    desc_div = li.find("div", class_="description")
                    if desc_div:
                        discs = parse_extras(desc_div.decode_contents())
                    break

            releases.append(
                Release(name=release_name, year=release_year, discs=discs)
            )

    return FilmComparison(
        title=title,
        year=year,
        format=disc_format,
        director=director,
        imdb_url=imdb_url,
        imdb_id=imdb_id,
        film_id=film_id,
        releases=releases,
    )


def parse_search_results(html: str) -> list[SearchResult]:
    """Parse a dvdcompare.net search results page."""
    soup = BeautifulSoup(html, "html.parser")
    results: list[SearchResult] = []
    seen: set[int] = set()

    for link in soup.find_all("a", href=re.compile(r"film\.php\?fid=\d+")):
        text = link.get_text(strip=True)
        if not text:
            continue
        href = link["href"]
        fid_match = re.search(r"fid=(\d+)", href)
        film_id = int(fid_match.group(1)) if fid_match else None

        if film_id and film_id in seen:
            continue
        if film_id:
            seen.add(film_id)

        if not href.startswith("http"):
            href = f"https://www.dvdcompare.net/comparisons/{href}"

        results.append(SearchResult(title=text, url=href, film_id=film_id))

    return results
