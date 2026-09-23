#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


DEFAULT_INPUT_PATH = Path("public/911-addresses.parquet")
DEFAULT_COUNTIES_PATH = Path("public/counties-exact.gpkg")
DEFAULT_DISTRICTS_PATH = Path("public/legislative-districts-exact.gpkg")
DEFAULT_POLLING_PLACES_PATH = Path("public/polling-places-nodups.csv")
DEFAULT_WHERE_TO_VOTE_DIR = (
    Path.home() / "Box/dsi-core/11th-hour/ndnv-address-lookup/where-to-vote-2026"
)
DEFAULT_WHERE_TO_VOTE_POINTS_PATH = DEFAULT_WHERE_TO_VOTE_DIR / "wheretovote-points.gpkg"
DEFAULT_WHERE_TO_VOTE_AREAS_PATH = (
    DEFAULT_WHERE_TO_VOTE_DIR / "wheretovote-polling-areas.gpkg"
)

COMPRESSION = "zstd"
COMPRESSION_LEVEL = 22
COLUMN_ENCODING = {
    "num": "PLAIN",
    "street": "PLAIN",
    "unit": "PLAIN",
    "muni": "PLAIN",
    "msag": "PLAIN",
    "zip": "PLAIN",
    "src": "PLAIN",
    "lon": "BYTE_STREAM_SPLIT",
    "lat": "BYTE_STREAM_SPLIT",
    "county_fp": "PLAIN",
    "district": "PLAIN",
}
DICTIONARY_COLUMNS = ["polling_places"]

# The shipped column order, pinned deliberately. src/lib/AddressesLayer.svelte reads
# the Parquet by an explicit column list and then indexes the result POSITIONALLY
# (row[0]..row[12]), so a reordered schema risks putting e.g. a district string where
# a latitude is expected. Appending in a different order is easy to do by accident:
# it depends on which of these four columns the input already had.
FINAL_COLUMN_ORDER = [
    "num",
    "street",
    "unit",
    "muni",
    "msag",
    "zip",
    "src",
    "lon",
    "lat",
    "district",
    "in_wheretovote",
    "polling_places",
    "county_fp",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help="Input parquet file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output parquet file (defaults to overwriting the input)",
    )
    parser.add_argument(
        "--counties",
        type=Path,
        default=DEFAULT_COUNTIES_PATH,
        help="GeoPackage with county polygons and county_fp values",
    )
    parser.add_argument(
        "--districts",
        type=Path,
        default=DEFAULT_DISTRICTS_PATH,
        help="GeoPackage with legislative district polygons",
    )
    parser.add_argument(
        "--polling-places",
        type=Path,
        default=DEFAULT_POLLING_PLACES_PATH,
        help="CSV with canonical polling place rows",
    )
    parser.add_argument(
        "--wheretovote-points",
        type=Path,
        default=DEFAULT_WHERE_TO_VOTE_POINTS_PATH,
        help="GeoPackage with exact point assignments",
    )
    parser.add_argument(
        "--wheretovote-areas",
        type=Path,
        default=DEFAULT_WHERE_TO_VOTE_AREAS_PATH,
        help="GeoPackage with polygon-based polling place assignments",
    )
    return parser.parse_args()


def get_row_group_sizes(parquet_path: Path) -> list[int]:
    parquet_file = pq.ParquetFile(parquet_path)
    metadata = parquet_file.metadata
    return [metadata.row_group(i).num_rows for i in range(metadata.num_row_groups)]


def load_dataframe(parquet_path: Path) -> pd.DataFrame:
    return pd.read_parquet(parquet_path)


def assign_districts(dataframe: pd.DataFrame, districts_path: Path) -> pd.DataFrame:
    districts = gpd.read_file(districts_path)[["district", "geometry"]]
    points = gpd.GeoDataFrame(
        dataframe[["lon", "lat"]].copy(),
        geometry=gpd.points_from_xy(dataframe["lon"], dataframe["lat"]),
        crs=districts.crs,
    )
    joined = gpd.sjoin(points, districts, how="left", predicate="within")

    if joined.index.has_duplicates:
        raise RuntimeError("District join produced duplicate address rows")
    if joined["district"].isna().any():
        missing = int(joined["district"].isna().sum())
        raise RuntimeError(f"District join failed for {missing} addresses")

    dataframe = dataframe.copy()
    dataframe["district"] = joined["district"].astype(str).str.strip().str.ljust(2, " ")
    if (dataframe["district"].str.len() != 2).any():
        raise RuntimeError("District values are not fixed-width after padding")
    return dataframe


def assign_county_fp(dataframe: pd.DataFrame, counties_path: Path) -> pd.DataFrame:
    counties = gpd.read_file(counties_path)[["county_fp", "geometry"]]
    points = gpd.GeoDataFrame(
        dataframe[["lon", "lat"]].copy(),
        geometry=gpd.points_from_xy(dataframe["lon"], dataframe["lat"]),
        crs=counties.crs,
    )
    joined = gpd.sjoin(points, counties, how="left", predicate="within")

    if joined.index.has_duplicates:
        raise RuntimeError("County join produced duplicate address rows")
    if joined["county_fp"].isna().any():
        missing = int(joined["county_fp"].isna().sum())
        raise RuntimeError(f"County join failed for {missing} addresses")

    county_fp = pd.to_numeric(joined["county_fp"], errors="raise")
    if ((county_fp < 0) | (county_fp > 255)).any():
        raise RuntimeError("county_fp values are out of range for uint8")

    dataframe = dataframe.copy()
    dataframe["county_fp"] = county_fp.astype("uint8")
    return dataframe


def load_polling_place_lookup(polling_places_path: Path) -> tuple[pd.DataFrame, dict[str, int]]:
    polling_places = pd.read_csv(polling_places_path, dtype=str).fillna("")
    keys = (
        polling_places["polling_location"]
        + ", "
        + polling_places["address"]
        + ", "
        + polling_places["city"]
        + ", "
        + polling_places["zip_code"]
    )
    lookup = {value: index for index, value in enumerate(keys)}
    if len(lookup) != len(polling_places):
        raise RuntimeError("Polling-place lookup keys are not unique")
    return polling_places, lookup


def polling_min_to_index_string(polling_min: str, lookup: dict[str, int]) -> str:
    indexes = sorted({lookup[value] for value in json.loads(polling_min)})
    return " ".join(str(index) for index in indexes)


def normalize_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype("Int64")


def load_wheretovote_points(
    wheretovote_points_path: Path, lookup: dict[str, int], addresses: pd.DataFrame
) -> pd.DataFrame:
    points = gpd.read_file(
        wheretovote_points_path,
        layer="wheretovote-points",
        columns=["index", "num", "street", "zip", "polling_min"],
    ).copy()

    if points["index"].isna().any():
        missing = int(points["index"].isna().sum())
        raise RuntimeError(f"WhereToVote points contain {missing} null indexes")

    points["index"] = points["index"].astype(int)
    if points["index"].duplicated().any():
        duplicated = points.loc[points["index"].duplicated(keep=False), "index"]
        raise RuntimeError(
            f"WhereToVote points contain duplicate indexes, including {duplicated.iloc[0]}"
        )
    if ((points["index"] < 0) | (points["index"] >= len(addresses))).any():
        raise RuntimeError("WhereToVote points contain out-of-bounds indexes")

    matched = addresses.iloc[points["index"].to_numpy()].reset_index(drop=True)
    points = points.reset_index(drop=True)

    if not normalize_num(points["num"]).equals(normalize_num(matched["num"])):
        raise RuntimeError("WhereToVote points num values do not match 911 addresses")
    if not points["street"].astype(str).equals(matched["street"].astype(str)):
        raise RuntimeError("WhereToVote points street values do not match 911 addresses")
    if not points["zip"].astype(str).equals(matched["zip"].astype(str)):
        raise RuntimeError("WhereToVote points zip values do not match 911 addresses")

    points["polling_places"] = points["polling_min"].apply(
        lambda value: polling_min_to_index_string(value, lookup)
    )
    return points[["index", "polling_places"]].sort_values("index").reset_index(drop=True)


def load_wheretovote_areas(
    wheretovote_areas_path: Path, lookup: dict[str, int], addresses: pd.DataFrame
) -> pd.Series:
    areas = gpd.read_file(
        wheretovote_areas_path,
        layer="wheretovote-polling-areas",
        columns=["polling_min", "geometry"],
    ).copy()
    areas["polling_places"] = areas["polling_min"].apply(
        lambda value: polling_min_to_index_string(value, lookup)
    )

    points = gpd.GeoDataFrame(
        pd.DataFrame(index=addresses.index),
        geometry=gpd.points_from_xy(addresses["lon"], addresses["lat"]),
        crs=areas.crs,
    )
    joined = gpd.sjoin(
        points,
        areas[["polling_places", "geometry"]],
        how="left",
        predicate="within",
    )

    if joined.index.has_duplicates:
        duplicated = joined.index[joined.index.duplicated(keep=False)]
        raise RuntimeError(
            f"Polling-area join produced duplicate address rows, including index {duplicated[0]}"
        )

    result = pd.Series("", index=addresses.index, dtype=object)
    matched = joined["polling_places"].dropna()
    result.loc[matched.index] = matched.astype(str)
    return result


def assign_wheretovote_fields(
    dataframe: pd.DataFrame,
    wheretovote_points_path: Path,
    wheretovote_areas_path: Path,
    polling_places_path: Path,
) -> pd.DataFrame:
    _, lookup = load_polling_place_lookup(polling_places_path)
    points = load_wheretovote_points(wheretovote_points_path, lookup, dataframe)
    areas = load_wheretovote_areas(wheretovote_areas_path, lookup, dataframe)

    dataframe = dataframe.copy()
    dataframe["in_wheretovote"] = False
    dataframe.loc[points["index"], "in_wheretovote"] = True
    dataframe["polling_places"] = ""

    points_polling_places = pd.Series(
        points["polling_places"].to_numpy(),
        index=points["index"].to_numpy(),
        dtype=object,
    )

    area_mask = areas != ""
    overlap_index = points_polling_places.index.intersection(areas.index[area_mask])
    disagreement_index = overlap_index[
        points_polling_places.loc[overlap_index].to_numpy()
        != areas.loc[overlap_index].to_numpy()
    ]
    if len(disagreement_index) != 0:
        bad_index = int(disagreement_index[0])
        raise RuntimeError(
            "WhereToVote points and polling areas disagree for "
            f"911-address row {bad_index}: "
            f"{points_polling_places.loc[bad_index]!r} vs {areas.loc[bad_index]!r}"
        )

    # Fill from the inferred polygons first, then let the addresses WhereToVote
    # answered directly override.
    #
    # Filling from `areas` alone silently discarded 533 official answers: an address
    # that WhereToVote DOES have an answer for still ended up blank whenever it fell
    # outside every polygon, which happens because
    # remove_small_polling_area_components() deliberately drops simply-connected
    # components with fewer than --min-addresses points. Dropping a shaky *inference*
    # is right; dropping the state's own answer for that address is not.
    #
    # The disagreement check above has already proven the two sources agree wherever
    # they overlap, so this is purely additive.
    dataframe.loc[area_mask, "polling_places"] = areas.loc[area_mask]
    dataframe.loc[points_polling_places.index, "polling_places"] = points_polling_places
    return dataframe


def build_output_schema(input_schema: pa.Schema) -> pa.Schema:
    added = {
        "county_fp": pa.field("county_fp", pa.uint8()),
        "district": pa.field("district", pa.string()),
        "in_wheretovote": pa.field("in_wheretovote", pa.bool_()),
        "polling_places": pa.field("polling_places", pa.string()),
    }
    by_name = {field.name: field for field in input_schema}
    for name, field in added.items():
        by_name.setdefault(name, field)

    unexpected = set(by_name) - set(FINAL_COLUMN_ORDER)
    if unexpected:
        raise RuntimeError(
            f"unexpected column(s) {sorted(unexpected)}; add them to "
            f"FINAL_COLUMN_ORDER so the order the app reads stays pinned"
        )
    missing = set(FINAL_COLUMN_ORDER) - set(by_name)
    if missing:
        raise RuntimeError(f"input is missing column(s) {sorted(missing)}")

    fields = [by_name[name] for name in FINAL_COLUMN_ORDER]
    return pa.schema(fields, metadata=input_schema.metadata)


def dataframe_to_table(dataframe: pd.DataFrame, schema: pa.Schema) -> pa.Table:
    table = pa.Table.from_pandas(dataframe, schema=schema, preserve_index=False)
    return table.replace_schema_metadata(schema.metadata)


def write_table_with_existing_layout(
    table: pa.Table, row_group_sizes: list[int], output_path: Path
) -> None:
    writer = pq.ParquetWriter(
        output_path,
        schema=table.schema,
        compression=COMPRESSION,
        compression_level=COMPRESSION_LEVEL,
        column_encoding=COLUMN_ENCODING,
        use_dictionary=DICTIONARY_COLUMNS,
    )
    try:
        start = 0
        for row_group_size in row_group_sizes:
            for batch in table.slice(start, row_group_size).to_batches():
                writer.write_batch(batch)
            start += row_group_size
    finally:
        writer.close()


def main() -> int:
    args = parse_args()
    input_path = args.input
    output_path = args.output if args.output is not None else input_path

    parquet_file = pq.ParquetFile(input_path)
    input_schema = parquet_file.schema_arrow
    row_group_sizes = get_row_group_sizes(input_path)
    dataframe = load_dataframe(input_path)
    dataframe = assign_county_fp(dataframe, args.counties)
    dataframe = assign_districts(dataframe, args.districts)
    dataframe = assign_wheretovote_fields(
        dataframe,
        wheretovote_points_path=args.wheretovote_points,
        wheretovote_areas_path=args.wheretovote_areas,
        polling_places_path=args.polling_places,
    )
    schema = build_output_schema(input_schema)
    table = dataframe_to_table(dataframe, schema)
    write_table_with_existing_layout(table, row_group_sizes, output_path)

    print(f"Loaded {len(dataframe)} rows from {input_path}")
    print(f"Assigned county_fp from {args.counties}")
    print(f"Assigned districts from {args.districts}")
    print(f"Assigned WhereToVote fields from {args.wheretovote_points}")
    print(f"Assigned polling-area fields from {args.wheretovote_areas}")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
