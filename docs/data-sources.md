# Data sources

Provenance for every dataset the web app loads. Assembled from the scripts, the GitHub
issue/PR history, and the September 2026 re-check; several entries had no recorded source
anywhere before this document.

"Fetched" is the date of the data currently in the repo.

## Voting data — ND Secretary of State

All from `https://vip.sos.nd.gov/Precincts.aspx?eid=<eid>`, an ASP.NET/Telerik page whose six
tabs share one URL. `scripts/step1-update-polling-places.py` selects a tab by replaying the
Telerik client-state in the "Export to Excel" postback. **The eid identifies one election** —
`346` = June 9, 2026 primary, `348` = November 3, 2026 general.

The data is scraped rather than queried live because `vip.sos.nd.gov` sends no CORS headers, so
the browser cannot call it from `myaddress.ndnativevote.org` (tested in
`uchicago-dsi/core-facility#124`).

| File | Tab | Fetched | Notes |
|---|---|---|---|
| `public/polling-places.parquet` | 5 | 2026-09-02, `eid=348` | All 11 columns. Not read by the browser; used by steps 2 and 3. |
| `public/polling-places-nodups.csv` | 5 | 2026-09-02, `eid=348` | Slim + de-duplicated. **Row order is load-bearing** — the Parquet's `polling_places` column indexes it by position. |
| `public/dropboxes.csv` | 2 | 2026-09-02, `eid=348` | `County Number` converted to Census-style `county_fp = 2n − 1`. |
| `public/early-voting.csv` | 4 | 2026-09-02, `eid=348` | Added Sept 2026. The tab has no county number, so it is joined from the other tabs. |

`scripts/precincts-supplement.json` carries counties that the export omits but WhereToVote
publishes (Rolette as of 2026-09-02), and counties confirmed to have no polling places
established (Ransom). Each entry records why and how it was verified.

### Precinct assignment per address

`https://vip.sos.nd.gov/WhereToVote.aspx`, scraped once per address by
`scripts/step0-*` in March 2026 (431,238 queries) and stored in Box as
`where-to-vote-2026/fetch-WhereToVote/key-value-pairs.csv`.

WhereToVote's answer depends only on `(house number, ZIP, street)` and is
**election-independent**, so it does not need re-scraping when the election changes — only the
precinct → polling-place join does. After an address rebuild it is re-pointed onto the new row
positions by `scripts/rekey-wheretovote-scrape.py`.

### Polling-place coordinates

`public/polling-places-locations.json`, `dropboxes-locations.json`,
`early-voting-locations.json` — name → `[lon, lat]`.

Geocoded by `scripts/geocode-polling-places.py` via the Census geocoder
(`geocoding.geo.census.gov`, benchmark `Public_AR_Current`) with Nominatim as a fallback, then
**verified by hand**, satellite imagery and Street View. Coordinates rather than place names are
used for directions so the links do not change meaning when Google's name database does.

## 911 addresses — ND GIS Hub

`public/911-addresses.parquet`, 438,257 addresses, fetched **2026-10-26** (layer last edited
2026-10-26). This is the first export with any Sioux County addresses (1,725).

- Portal: <https://gishubdata-ndgov.hub.arcgis.com/datasets/NDGOV::ndgishub-site-structure-address-points>
- Service: `services1.arcgis.com/GOcSXpzwBHyk2nog/…/NDGISHUBSiteStructureAddressPoints/FeatureServer/0`
- GeoPackage export: `hub.arcgis.com/api/download/v1/items/7c825491a88b4c03b22fde12eee38f83/geopackage`
- Built by `scripts/build-911-addresses.py`; enriched by steps 2 and 3.

The companion **Roads NG911** layer was evaluated in 2025 and rejected: points alone were
sufficient, and dropping roads greatly reduced file size and search complexity.

Deliberate choices: house number `0` is kept (it can be legitimate); ZIP+4 is dropped; addresses
are **not** de-duplicated, because "if a user sees their house and there's no dot on it, we have
failed" (issue #27). Column derivations are documented in the build script.

Attribution appears in the map's attribution control (`AddressesLayer.svelte`) and in the welcome
dialog (`Welcome.svelte`).

## 911 coordinator contacts

`src/data/source-list.json` — 55 records, the contact shown in each popup's "Source" section.

Sources, all verified **2026-09-02**:

- The 53 county entries: the NDACo County Officials Directory,
  <https://www.ndaco.org/cod/browse-by-position/#/position/911%20Coordinator>. 16 entries had
  stale name/phone/email and 2 had a stale `title`; all 53 now match on every field.
- Index 9 `CITY OF BISMARCK 911`: the City of Bismarck CenCom staff directory,
  <https://www.bismarcknd.gov/directory.aspx?did=5>.
- Index 10 `CITY OF GRAND FORKS 911`: the City of Grand Forks Fire Department administrative
  staff page, <https://www.grandforksgov.com/government/city-departments/fire/staff>. Its `name`
  is intentionally a placeholder — the city no longer staffs a 911-coordinator role.

Caveat for future re-checks: NDACo is an aggregator, not each county's own record, so it can lag.
The two city entries have to be checked separately because NDACo lists only county officials.

**Array position is an interface.** The Parquet's `src` column indexes this file positionally.
Index 43 (`SIOUX COUNTY 911`) was reserved, unused, until Sioux County addresses appeared in
October 2026; it is now used by those 1,725 rows. Index 54 is intentionally out of
alphabetical order. Edit in place; never sort.

## Legislative districts — ND Legislative Council

- `public/legislative-districts-exact.gpkg` (48 features, EPSG:4269) — build-time input.
- `public/legislative-districts.geojson` — simplified web copy; **currently unused by the app**.

Source: <https://ndlegis.gov/districts/2025-2032>, file
`downloads/2025-districts/final-court-ordered-map-shape-files.zip`. Fetched 2026-03-18;
re-confirmed unchanged 2026-09-02 (the zip's `last-modified` is 2024-05-28). The 2025-2032 map
runs through 2032, so it should not change before this election.

Popup links go to `https://ndlegis.gov/districts/2025-2032/district-<N>`, with a trailing `A`/`B`
subdistrict letter stripped.

## Counties — U.S. Census

- `public/counties.geojson` (53 features, `name` only) — display; simplified to 10 m and written
  with 4 decimal places.
- `public/counties-exact.gpkg` (`county`, `county_fp`) — build-time input for the spatial joins.

From the Census county boundaries; the 2025 file was reused in 2026 rather than re-fetched.
Unchanged 2026-09-02 — North Dakota has had no county boundary changes.

## Census tracts — U.S. Census TIGER 2024

<https://www2.census.gov/geo/tiger/TIGER2024/TRACT/tl_2024_38_tract.zip> (228 features, 208
distinct `TRACTCE`).

Not shipped, but it **defines the Parquet row groups** for both the addresses and the small
roads, which is what keeps browser memory bounded. Changing the vintage re-orders every row.

## Roads — OpenStreetMap via Geofabrik

- `public/osm-big-roads.geojson` — motorway/trunk/primary/secondary, loaded at startup.
- `public/osm-small-roads.parquet` — everything else, one row group per census tract, read on
  demand.

Source: <https://download.geofabrik.de/north-america/us/north-dakota.html>
(`gis_osm_roads_free_1.shp`), built by `scripts/osm-roads-to-parquet.py`. Fetched 2025-06-16.

OSM was chosen over Census TIGER roads after a side-by-side comparison (PR #7): the Census data
was incomplete in both urban Bismarck and rural Sioux County, and often lacked names. Geometry is
simplified to 5 m — 10 m was tested and rejected for flattening cul-de-sacs.

## Basemap

Satellite raster tiles from `https://mt1.google.com/vt/lyrs=s` (`minzoom` 10), attributed to
Google Maps in `src/data/map-style.json`. Previous iterations used USGS imagery, OpenMapTiles
vector tiles, and MapBox-hosted tilesets; all were dropped (issues #16, #27, #29).

## Provenance still incomplete

No upstream URL or fetch date is recorded anywhere for these, and no script generates them. They
are not election-dependent, so the September 2026 re-check left them alone — but the gap should be
closed if any of them ever needs regenerating.

| File | What is known |
|---|---|
| `public/reservations.geojson` | 5 reservations; simplified to 10 m and 4 decimals like the counties (PR #3). Source unrecorded. |
| `public/places.geojson` | 1,886 points with `name` + `minzoom`; added in PR #28. Either Census "Places" or the OSM places layer — issue #4 discusses both, and neither was recorded as chosen. |
| `src/data/ND-*.json` | Search index: counties, places, townships, ZIP codes, reservations. Sources unrecorded. |
| `public/sprites.*`, `public/fonts/` | Highway shields and glyph PBFs, added with the road work. Mostly a third-party POI sprite atlas of which only the shields are used. |
