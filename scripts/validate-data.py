#!/usr/bin/env python3
"""Check the invariants the web app depends on. Run after any data refresh.

Every check here corresponds to a way the app can silently show a voter the wrong
polling place, or blow its memory budget on a phone. Failures are errors; things
worth a human look are warnings.
"""

import argparse
import csv
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parent.parent
PUBLIC = REPO_ROOT / "public"

# src/lib/AddressesLayer.svelte reads these by name and then indexes the result
# positionally, so the order is part of the contract.
EXPECTED_COLUMNS = [
    "num", "street", "unit", "muni", "msag", "zip", "src", "lon", "lat",
    "district", "in_wheretovote", "polling_places", "county_fp",
]
EXPECTED_TYPES = [
    "int32", "string", "string", "string", "string", "string", "int8", "float",
    "float", "string", "bool", "string", "uint8",
]

# The election this data is for. Free text mentioning a date outside the window
# between absentee opening and election day is almost always left over from the
# previous election -- in September 2026 a Cavalier County drop-box row still told
# voters their ballot was due "June 9th, 2026", and shipped that way for 3 weeks.
ELECTION_DAY = datetime.date(2026, 11, 3)
ABSENTEE_OPENS = datetime.date(2026, 9, 24)

MONTHS = {m.lower(): i for i, m in enumerate(
    ["January","February","March","April","May","June","July","August",
     "September","October","November","December"], start=1)}
DATE_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+(\d{1,2})(?:st|nd|rd|th)?\b(?:[,\s]+(\d{4}))?",
    re.I)

errors: list[str] = []
warnings: list[str] = []


def stale_dates(text: str) -> list[str]:
    """Month-day references that fall outside the current election window."""
    out = []
    for month_name, day, year in DATE_RE.findall(text or ""):
        month = MONTHS[month_name.lower()]
        try:
            found = datetime.date(int(year) if year else ELECTION_DAY.year, month, int(day))
        except ValueError:
            continue
        if not (ABSENTEE_OPENS <= found <= ELECTION_DAY):
            out.append(f"{month_name} {day}" + (f", {year}" if year else ""))
    return out


def check(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def warn(condition: bool, message: str) -> None:
    if not condition:
        warnings.append(message)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    addresses = pq.ParquetFile(PUBLIC / "911-addresses.parquet")
    schema = addresses.schema_arrow
    meta = addresses.metadata

    # --- Parquet structure: the serverless tiling scheme -------------------------
    check(
        list(schema.names) == EXPECTED_COLUMNS,
        f"911-addresses.parquet column ORDER changed: {list(schema.names)}. The app "
        f"indexes columns positionally; see FINAL_COLUMN_ORDER in step3.",
    )
    check(
        [str(t) for t in schema.types] == EXPECTED_TYPES,
        f"911-addresses.parquet column types changed: {[str(t) for t in schema.types]}",
    )
    check(
        150 <= meta.num_row_groups <= 260,
        f"911-addresses.parquet has {meta.num_row_groups} row groups; expected one per "
        f"census tract (~206). One big row group would restore the ~800 MB memory bug.",
    )
    for group in range(min(meta.num_row_groups, 5)):
        row_group = meta.row_group(group)
        for index in range(row_group.num_columns):
            column = row_group.column(index)
            if column.path_in_schema in ("lon", "lat"):
                check(
                    column.is_stats_set,
                    f"row group {group} has no {column.path_in_schema} statistics; the "
                    f"browser prunes row groups by these and would read all of them.",
                )
    encodings = {}
    row_group = meta.row_group(0)
    for index in range(row_group.num_columns):
        column = row_group.column(index)
        encodings[column.path_in_schema] = (column.compression, set(column.encodings))
    check(
        all(value[0] == "ZSTD" for value in encodings.values()),
        f"911-addresses.parquet is not all ZSTD: "
        f"{ {k: v[0] for k, v in encodings.items()} }",
    )
    for name in ("lon", "lat"):
        check(
            "BYTE_STREAM_SPLIT" in encodings[name][1],
            f"{name} lost BYTE_STREAM_SPLIT encoding (file will be much larger)",
        )
    check(
        "RLE_DICTIONARY" in encodings["polling_places"][1],
        "polling_places lost its dictionary encoding",
    )
    for name in EXPECTED_COLUMNS:
        if name in ("lon", "lat", "polling_places"):
            continue
        check(
            "RLE_DICTIONARY" not in encodings[name][1],
            f"{name} is dictionary-encoded but should be PLAIN",
        )

    table = addresses.read()
    rows = table.num_rows

    # --- polling_places indexes into polling-places-nodups.csv ------------------
    polling_places = read_csv(PUBLIC / "polling-places-nodups.csv")
    limit = len(polling_places)
    bad_index = 0
    empty = 0
    for value in table.column("polling_places").to_pylist():
        if value == "":
            empty += 1
            continue
        for piece in value.split():
            if not piece.isdigit() or not (0 <= int(piece) < limit):
                bad_index += 1
    check(
        bad_index == 0,
        f"{bad_index} polling_places entries are out of range for the "
        f"{limit}-row polling-places-nodups.csv. Regenerating that CSV without "
        f"re-running step3 silently repoints every address.",
    )
    warn(
        empty / rows < 0.05,
        f"{empty:,} of {rows:,} addresses ({100 * empty / rows:.1f}%) have no polling "
        f"place at all",
    )

    # --- src indexes into source-list.json --------------------------------------
    source_list = json.loads((REPO_ROOT / "src/data/source-list.json").read_text())
    src_values = table.column("src").to_pylist()
    check(
        min(src_values) >= 0 and max(src_values) < len(source_list),
        f"src ranges {min(src_values)}..{max(src_values)} but source-list.json has "
        f"{len(source_list)} entries",
    )
    check(
        len({record["src"] for record in source_list}) == len(source_list),
        "source-list.json has duplicate 'src' values",
    )
    for position, record in enumerate(source_list):
        warn(
            bool(record["phone"] or record["email"]),
            f"source-list.json[{position}] ({record['src']}) has neither phone nor email",
        )

    # --- county_fp joins to dropboxes.csv / early-voting.csv --------------------
    county_fps = set(table.column("county_fp").to_pylist())
    for name, filename in (("dropboxes", "dropboxes.csv"), ("early voting", "early-voting.csv")):
        path = PUBLIC / filename
        if not path.exists():
            warnings.append(f"{filename} is missing")
            continue
        file_fps = {int(row["county_fp"]) for row in read_csv(path)}
        unreachable = sorted(file_fps - county_fps)
        warn(
            not unreachable,
            f"{filename}: county_fp {unreachable} has no addresses, so those {name} "
            f"locations can never be shown by tapping an address",
        )

    # --- location names must resolve to coordinates, 1 name : 1 address ---------
    for csv_name, name_column, json_name in (
        ("polling-places-nodups.csv", "polling_location", "polling-places-locations.json"),
        ("dropboxes.csv", "polling_location", "dropboxes-locations.json"),
        ("early-voting.csv", "early_voting_location", "early-voting-locations.json"),
    ):
        csv_path, json_path = PUBLIC / csv_name, PUBLIC / json_name
        if not csv_path.exists() or not json_path.exists():
            warnings.append(f"{csv_name} or {json_name} is missing")
            continue
        records = read_csv(csv_path)
        locations = json.loads(json_path.read_text())

        by_name: dict[str, set[tuple[str, str, str]]] = {}
        for record in records:
            by_name.setdefault(record[name_column], set()).add(
                (record["address"], record["city"], record["zip_code"])
            )
        for name, addresses_for_name in sorted(by_name.items()):
            check(
                len(addresses_for_name) == 1,
                f"{csv_name}: {name!r} maps to {len(addresses_for_name)} different "
                f"addresses {sorted(addresses_for_name)}; coordinates are keyed by name "
                f"alone, so directions would point at the wrong one",
            )
        no_coordinates = sorted(set(by_name) - set(locations))
        warn(
            not no_coordinates,
            f"{json_name}: no coordinates for {no_coordinates} (these render as plain "
            f"text with no directions link)",
        )
        for name, coordinate in locations.items():
            check(
                isinstance(coordinate, list)
                and len(coordinate) == 2
                and -105 < coordinate[0] < -95
                and 45 < coordinate[1] < 49.5,
                f"{json_name}: {name!r} coordinate {coordinate} is outside North Dakota "
                f"(expected [lon, lat])",
            )

    # --- an official answer must never be dropped ------------------------------
    in_wheretovote = table.column("in_wheretovote").to_pylist()
    polling_column = table.column("polling_places").to_pylist()
    official_blank = sum(
        1 for flag, value in zip(in_wheretovote, polling_column) if flag and value == ""
    )
    check(
        official_blank == 0,
        f"{official_blank} address(es) have in_wheretovote=True but no polling place. "
        f"WhereToVote gave a definitive answer for them and the app would show nothing. "
        f"Cause to look for: step3 filling polling_places only from the inferred "
        f"polygons, which drops small components on purpose.",
    )

    # --- free text must not cite the previous election --------------------------
    for filename, name_column, text_columns in (
        ("dropboxes.csv", "polling_location", ("polling_hours",)),
        ("early-voting.csv", "early_voting_location", ("early_voting_times", "comments")),
        ("polling-places-nodups.csv", "polling_location", ("polling_hours",)),
    ):
        path = PUBLIC / filename
        if not path.exists():
            continue
        for record in read_csv(path):
            for column in text_columns:
                for found in stale_dates(record.get(column, "")):
                    errors.append(
                        f"{filename}: {record.get('county','?')} / "
                        f"{record[name_column]!r} ({column}) mentions {found!r}, which is "
                        f"outside {ABSENTEE_OPENS}..{ELECTION_DAY}. Left over from a "
                        f"previous election?"
                    )

    # --- a renamed address must not keep a stale coordinate ---------------------
    # The geocoder is incremental BY NAME, so a location that moved but kept its
    # name silently keeps its old coordinate. Compare against the committed copy.
    for filename, name_column in (
        ("polling-places-nodups.csv", "polling_location"),
        ("dropboxes.csv", "polling_location"),
        ("early-voting.csv", "early_voting_location"),
    ):
        try:
            committed = subprocess.run(
                ["git", "show", f"HEAD:public/{filename}"],
                cwd=REPO_ROOT, capture_output=True, text=True, check=True,
            ).stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
        before = {
            r[name_column]: (r["address"], r["city"])
            for r in csv.DictReader(committed.splitlines())
        }
        for record in read_csv(PUBLIC / filename):
            was = before.get(record[name_column])
            now = (record["address"], record["city"])
            if was is not None and was != now:
                warn(
                    False,
                    f"{filename}: {record[name_column]!r} kept its name but its address "
                    f"changed {was} -> {now}. The geocoder skips names it already has, so "
                    f"re-verify its coordinate.",
                )

    # --- every map label must be renderable with the glyph ranges we ship -------
    # The app bundles only the 0-255 .pbf range per font. A character outside it
    # makes maplibre request a glyph range that does not exist (404) and the
    # character fails to draw. In September 2026 the Sioux County label used an
    # em dash and 404'd on every render.
    style_path = REPO_ROOT / "src/data/map-style.json"
    fonts_dir = PUBLIC / "fonts"
    if style_path.exists() and fonts_dir.is_dir():
        available = {}
        for font_dir in fonts_dir.iterdir():
            if font_dir.is_dir():
                ranges = set()
                for pbf in font_dir.glob("*.pbf"):
                    start, _, end = pbf.stem.partition("-")
                    if start.isdigit() and end.isdigit():
                        ranges.add((int(start), int(end)))
                available[font_dir.name] = ranges

        style = json.loads(style_path.read_text())
        for layer in style.get("layers", []):
            layout = layer.get("layout") or {}
            text_field = layout.get("text-field")
            if not isinstance(text_field, str):
                continue
            fonts = layout.get("text-font") or []
            for character in set(text_field):
                if character in "{}\n" or ord(character) <= 255:
                    continue
                for font in fonts:
                    covered = any(
                        low <= ord(character) <= high
                        for low, high in available.get(font, set())
                    )
                    check(
                        covered,
                        f"map-style.json layer {layer['id']!r} uses {character!r} "
                        f"(U+{ord(character):04X}) in text-field, but {font!r} ships no glyph "
                        f"range covering it. maplibre will 404 and the character will not "
                        f"render. Use an ASCII character or ship the range.",
                    )

        # Label data feeds the same glyph pipeline via {name}.
        for filename, font in (("places.geojson", "Noto Sans Regular"),
                               ("counties.geojson", "Noto Sans Bold"),
                               ("reservations.geojson", "Noto Sans Bold")):
            path = PUBLIC / filename
            if not path.exists():
                continue
            ranges = available.get(font, set())
            for feature in json.loads(path.read_text()).get("features", []):
                name = feature.get("properties", {}).get("name") or ""
                for character in set(name):
                    if ord(character) <= 255:
                        continue
                    if not any(low <= ord(character) <= high for low, high in ranges):
                        warn(
                            False,
                            f"{filename}: {name!r} contains {character!r} "
                            f"(U+{ord(character):04X}), which {font!r} cannot render with the "
                            f"shipped glyph ranges; it will be blank on the map.",
                        )

    print(f"911-addresses.parquet: {rows:,} rows, {meta.num_row_groups} row groups")
    print(f"polling places: {limit} rows; source-list.json: {len(source_list)} entries")
    for message in warnings:
        print(f"WARN  {message}")
    for message in errors:
        print(f"ERROR {message}")
    if errors:
        print(f"\n{len(errors)} error(s)")
        return 1
    print(f"\nall checks passed ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
