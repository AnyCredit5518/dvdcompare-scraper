# dvdcompare-scraper

Python client for looking up disc content metadata from [dvdcompare.net](https://www.dvdcompare.net) — an invaluable resource for the physical media community that catalogs per-disc content breakdowns across regional releases.

> **Disclaimer**: This project is not affiliated with dvdcompare.net. All disc content data is owned by and sourced from [dvdcompare.net](https://www.dvdcompare.net). Please use responsibly and respect their servers.

## Install

```
pip install -e ".[dev]"
```

## Usage

Search by title:

```
dvdcompare "Oppenheimer"
```

Look up by dvdcompare film ID:

```
dvdcompare --id 66397
```

Look up by URL:

```
dvdcompare --url "https://www.dvdcompare.net/comparisons/film.php?fid=66397"
```

### Regional releases

Each dvdcompare page lists multiple regional releases (e.g. America, United Kingdom, Japan), each with its own disc contents and runtimes. By default, the CLI shows only the first release listed.

- `--release` selects a release by position (1-based) or by name keyword (case-insensitive substring match):
  ```
  dvdcompare --id 67210 --release 2
  dvdcompare --id 67210 --release america
  dvdcompare --id 67210 --release "united kingdom"
  ```
  If no release matches the keyword, the available release names are printed so you can retry.
- `--all-releases` shows every release:
  ```
  dvdcompare --id 67210 --all-releases
  ```
- `--json` outputs the data structure (respects `--release` filtering):
  ```
  dvdcompare --id 67210 --json
  dvdcompare --id 67210 --release america --json
  ```

### Filtering with external tools

For more complex filtering, pipe the JSON output through jq or PowerShell:

**jq:**
```bash
dvdcompare --id 67210 --json | jq '.releases |= map(select(.name | test("america"; "i")))'
```

**PowerShell:**
```powershell
dvdcompare --id 67210 --json | ConvertFrom-Json | ForEach-Object {
    $_.releases = $_.releases | Where-Object { $_.name -match "america" }
    $_ | ConvertTo-Json -Depth 10
}
```

## Data model

- `FilmComparison`: top-level object with title, year, format, director, IMDB info, and a list of `Release` objects.
- `Release`: a regional release with name (e.g. "Blu-ray ALL America - BBC"), year, and a list of `Disc` objects.
- `Disc`: a single disc with number, format (e.g. "Blu-ray 4K"), and a list of `Feature` objects.
- `Feature`: a bonus feature with title, runtime, type, year, technical notes, play-all flag, and optional children (for grouped features like "Making Of" collections or episode groups).

## Tests

```
py -m pytest tests/ -v
```
