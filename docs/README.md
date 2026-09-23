# Documentation

This app tells North Dakotans — especially Native Americans — the official 911 address they
need for voter ID, and where to vote. Getting that wrong could cost someone their vote, so the
data is held to one rule: **every claim the app makes must be traceable to an official source.**

| Document | What it is for |
|---|---|
| [`recheck-runbook.md`](recheck-runbook.md) | **Start here when refreshing the data.** Step-by-step procedure, written for someone with no prior context. |
| [`data-sources.md`](data-sources.md) | Where every shipped dataset comes from, and how it is processed. |
| [`known-gaps.md`](known-gaps.md) | What the app cannot tell you, and why. Read before promising anyone completeness. |
| [`2026-09-23-data-recheck.md`](2026-09-23-data-recheck.md) | Audit record of the second refresh, the day before absentee voting opened. Includes three process fixes. |
| [`2026-09-02-data-recheck.md`](2026-09-02-data-recheck.md) | Audit record of the first refresh: every discrepancy found and every decision taken. |

## The pipeline

Scripts are numbered in execution order. Only steps 1–4 are needed for a routine
polling-place refresh; steps 0 and 5 are for a full address rebuild.

| Script | Purpose |
|---|---|
| `scripts/step0-fetch-WhereToVote-districts.py` | Scrape one address's districts from WhereToVote. |
| `scripts/step0-batch-fetch-WhereToVote-districts.py` | Drive step 0 in parallel over every address. **Only needed for addresses never scraped before** — see the runbook. |
| `scripts/step1-update-polling-places.py [eid]` | Fetch polling places, drop boxes and early voting from the Secretary of State. Defaults to `eid=348` (Nov 3, 2026 general). |
| `scripts/geocode-polling-places.py` | Geocode location names to coordinates. Incremental; every new coordinate must be checked by hand. |
| `scripts/build-911-addresses.py` | Build the base address Parquet from the ND GIS Hub NG911 layer. |
| `scripts/rekey-wheretovote-scrape.py` | Re-point an existing WhereToVote scrape at a rebuilt address file. |
| `scripts/step2-analyze-wheretovote.py` | Join addresses to polling places and build the inferred polling areas. |
| `scripts/step3-add-wheretovote-to-addresses.py` | Add `county_fp`, `district`, `in_wheretovote`, `polling_places` to the address Parquet. |
| `scripts/validate-data.py` | Check every invariant the app depends on, including that no official answer is dropped, that no free text cites a previous election's dates, and that no location kept its name while changing address. **Run after any data change.** |

Large inputs and intermediates live in
`~/Box/dsi-core/11th-hour/ndnv-address-lookup/`, not in git.

## Two invariants that will silently corrupt the app

**1. `polling_places` holds row *positions*.** The `polling_places` column of
`public/911-addresses.parquet` is a space-separated list of 0-based row indexes into
`public/polling-places-nodups.csv`. Regenerating that CSV without re-running step 3 repoints
every address at a different polling place, with no error. `validate-data.py` range-checks it.

**2. `src` holds a row *position* too.** The `src` column indexes
`src/data/source-list.json` by array position. **Never reorder or sort that file** — index 43
(`SIOUX COUNTY 911`) is deliberately unused, and index 54 is deliberately out of alphabetical
order. Editing contact details in place is safe; re-sorting would make every popup cite the
wrong 911 coordinator.

## Parquet internals are load-bearing

`public/911-addresses.parquet` and `public/osm-small-roads.parquet` use Parquet row groups as a
serverless tiling scheme: the browser reads only the row groups whose lon/lat statistics
intersect the viewport (`src/lib/AddressesLayer.svelte`). Preserve all four properties on any
rebuild:

- **Row groups** — one per census tract (`TRACTCE` from TIGER 2024), 206 for addresses.
- **Sort order** — `TRACTCE, muni, msag, zip, src, street, num`, stable sort, on the *derived*
  (title-cased) values.
- **Encoding** — `PLAIN` for scalars, `BYTE_STREAM_SPLIT` for `lon`/`lat`, dictionary only for
  `polling_places`, format version 2.6.
- **Compression** — zstd level 22.

Build artifacts with the **base conda environment's** library versions. Do not pin an old
pyarrow to reproduce a previous file byte-for-byte; check *structure* instead
(`validate-data.py`, and `build-911-addresses.py --verify-against`). Expect the `created_by`
string and a couple of bytes per data page to differ between pyarrow versions — that is the
toolchain, not the data.

## Budgets

From issues #8, #20 and PR #7, in the project's stated priority order:

1. **Correct information.** Misleading someone into losing their vote would be catastrophic.
2. **Usable on a low-end device with a small screen** (reference: a low-end Galaxy A15; layouts
   tested down to 320×480, and historically 176×220).
3. **Usable on low network connectivity.** Everything except satellite tiles loads at startup.

| Budget | Target | Measured 2026-09-02 |
|---|---|---|
| Peak RAM on a phone | < 150 MB ceiling, ~70 MB observed | 39–41 MB steady state after GC; ~140 MB transient before collection |
| Total site (`dist`) | ~10 MB target | 18 MB (3.8 MB of it build-only GeoPackages that should move out of `public/`) |
| `911-addresses.parquet` | — | 2.32 MB for 435,480 addresses |
