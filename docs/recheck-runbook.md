# Data re-check runbook

Written for someone (or some agent) with the Chrome DevTools MCP but **no prior context**.
Follow it in order. It assumes nothing from previous runs except the files in this repo and in
`~/Box/dsi-core/11th-hour/ndnv-address-lookup/`.

## When to run this

N.D.C.C. § 16.1-07-15 lets a county change early voting up to the **64th day** before an
election. For November 3, 2026 that deadline was **August 31, 2026**, so county decisions are
frozen — but the Secretary of State's *data entry* lags behind them. As of 2026-09-02 three
counties were still incomplete.

Checkpoints for the 2026 general election:

- [x] **2026-09-02** — first pass (PR #35). See `2026-09-02-data-recheck.md`.
- [x] **2026-09-23** — before absentee voting opened. See `2026-09-23-data-recheck.md`.
- [ ] **Late October 2026** — final check.

Each pass so far has found something the previous one missed, so run every step even when the
cheap probes look quiet.

## Step 0 — Re-derive the election id. Never assume it.

`https://vip.sos.nd.gov/Precincts.aspx?eid=<N>` is scoped to **one election**.

Open <https://www.sos.nd.gov/elections/voter/elections-currentpast> and find the link labelled
"2026 General Election Statewide Polling Places and Precincts". Read the `eid` out of its href.

As of 2026-09-02: **`eid=346` is the June 9 primary, `eid=348` is the November 3 general.**
The app shipped primary data for five months because nobody re-checked this.

**A single eid's contents also drift.** The `eid=346` polling-place export went 1,140 rows
(2026-03-18) → 1,516 (2026-04-07) → 1,403 (2026-09-02), gaining and losing whole counties along
the way. So a stale local copy can differ from the same URL re-fetched later, and a county can
be *missing* simply because its auditor has not reported yet.

If the eid has changed, update the default in `scripts/step1-update-polling-places.py`.

## Step 1 — Cheap "did anything change?" probes

Run these before doing any real work. If all three are unchanged, only step 2 is needed.

```bash
# Legislative districts: is the court-ordered map file still the same?
curl -sI -A Mozilla https://ndlegis.gov/downloads/2025-districts/final-court-ordered-map-shape-files.zip | grep -i last-modified
# Expected: Tue, 28 May 2024 19:44:43 GMT  (unchanged since before the March 2026 fetch)

# 911 addresses: how many are there now, and when were they last edited?
curl -s 'https://services1.arcgis.com/GOcSXpzwBHyk2nog/arcgis/rest/services/NDGISHUBSiteStructureAddressPoints/FeatureServer/0?f=json' | python3 -c 'import json,sys,datetime; d=json.load(sys.stdin); e=d["editingInfo"]; print("lastEdit", datetime.datetime.utcfromtimestamp(e["dataLastEditDate"]/1000))'
curl -s 'https://services1.arcgis.com/GOcSXpzwBHyk2nog/arcgis/rest/services/NDGISHUBSiteStructureAddressPoints/FeatureServer/0/query?where=1%3D1&returnCountOnly=true&f=json'
# 2026-09-02 baseline: 435,480 features, dataLastEditDate 2026-08-31

# Has Sioux County finally appeared? (0 means the gap is still there)
curl -s "https://services1.arcgis.com/GOcSXpzwBHyk2nog/arcgis/rest/services/NDGISHUBSiteStructureAddressPoints/FeatureServer/0/query?where=County%3D%27SIOUX+COUNTY%27&returnCountOnly=true&f=json"
```

## Step 2 — Refresh polling places, drop boxes and early voting

```bash
python3 scripts/step1-update-polling-places.py 348      # use the eid from step 0
```

Writes `public/polling-places.parquet`, `public/polling-places-nodups.csv`,
`public/dropboxes.csv`, `public/early-voting.csv`.

**Read its output.** It prints `SUPPLEMENT: adding <county>` or `SKIP supplement: <county> is
now in the SOS export`. A `SKIP` means the state fixed an omission and you should re-verify and
delete that county from `scripts/precincts-supplement.json`.

### How the Secretary of State's pages work

They are ASP.NET/Telerik with self-modifying HTML — **use the Chrome DevTools MCP, not curl**,
for anything interactive. The six tabs on `Precincts.aspx` share one URL; `step1` selects one by
replaying the Telerik tab client-state in the "Export to Excel" postback:

| Tab | Contents |
|---|---|
| 0 | Election Administration Information (vote centers? vote by mail? early voting?) |
| 1 | County Polling Places (locations, no precinct mapping) |
| 2 | County Drop Boxes |
| 3 | Number of Precincts |
| 4 | Early Voting Available Counties |
| 5 | **Statewide Polling Places** (precinct → location; this is the one that matters) |

`WhereToVote.aspx` is the tool voters are actually pointed at. Search by house number + ZIP, then
the results grid's hidden first column is `smPrecinctPart`, which you can feed directly to
`https://vip.sos.nd.gov/WhereToVoteDetail.aspx?Part=<smPrecinctPart>`. Its heading says
`2026 General Election - Voting Information for...` when the county has reported, and
`This information has not been established at this time by the county` when it has not. **That
distinction is the whole basis for how gaps are handled.**

## Step 3 — Re-check the known gaps

See `known-gaps.md`. As of 2026-09-23 the Secretary of State has closed all of these except
Foster, and `scripts/precincts-supplement.json` is **empty**.

- [ ] **Foster County drop box** — still absent. The only remaining county gap.
- [ ] **Sioux County** — still zero address points statewide; the fallback box is still needed.
- [ ] **Porcupine Local District Buidling** — street-level coordinate only. Do **not** "fix" it
      from a name search or MapQuest (South Dakota / Selfridge respectively); see
      `known-gaps.md`.

**If the supplement is non-empty, diff before retiring an entry.** When `step1` prints
`SKIP supplement: <county> is now in the SOS export`, compare the export's rows against what the
supplement carried before deleting it — they are not necessarily the same. In September 2026 the
supplement carried Rolette's drop box as *Rolette County Courthouse, 102 2nd St NE*; by the time
the export caught up the county had changed it to *Rolette City Hall, 302 Main St*. Deleting the
entry without looking would have been right by luck; carrying it forward would have shipped a
stale location.

## Step 4 — Geocode any new locations

```bash
python3 scripts/geocode-polling-places.py
python3 scripts/geocode-polling-places.py --input public/dropboxes.csv  --output public/dropboxes-locations.json
python3 scripts/geocode-polling-places.py --input public/early-voting.csv --output public/early-voting-locations.json --name-column early_voting_location
```

Incremental — it skips names it already has, so it only geocodes genuinely new ones.

**Every new coordinate must be verified by hand.** The geocoders interpolate along road
centerlines and are wrong often enough to matter:

- Mandaree Community Center's address geocode landed in an empty field 300 m from the building.
- Sitting Bull College's landed 1.25 km south of the campus.
- Triumph West Church inherited a coordinate 205 m away in a residential block.

Method that worked: search Google Maps for `"<name> <address> <city> ND <zip>"` and accept the
coordinate **only if Google echoes back the same street address**; otherwise look at satellite
imagery. If you cannot establish a coordinate you believe, **leave it out** — the app renders the
address as plain text, which is honest, rather than linking to a guess.

Two cross-checks worth knowing:

- `validate-data.py` flags coordinates outside North Dakota, names mapping to two addresses, and
  **names whose address changed while the name stayed the same**. That last one matters because
  the geocoder is incremental *by name*: in September 2026 Ross Community Building moved from
  300 to 203 Main St and silently kept its old coordinate. When you see that warning, delete the
  name from the `*-locations.json` file and re-run the geocoder so it re-resolves.
- A "distance from the town centre" sanity check via Nominatim produces false alarms — it put
  Rolette City Hall "8.9 km from Rolette" because Nominatim's Rolette node is not the townsite.
  Cross-check against a **hand-verified location in the same town** instead; Rolette City Hall is
  72 m from the verified WWI Memorial Building.

## Step 5 — Only if the address count changed

Skip unless step 1 showed a materially different feature count.

```bash
# 5a. download the current layer as a GeoPackage (no paging needed)
curl -s 'https://hub.arcgis.com/api/download/v1/items/7c825491a88b4c03b22fde12eee38f83/geopackage?redirect=false&layers=0'
#     -> {"status":"Completed","resultUrl":"...gpkg"}; poll until Completed, then download the
#        resultUrl into Box. CHECK it is current: compare its gpkg_contents.last_change and
#        feature count against the service, because the Hub serves a cached replica.

# 5b. BLOCKING regression test: reproduce the shipped file from the April-2025 snapshot first
python3 scripts/build-911-addresses.py \
  ~/Box/dsi-core/11th-hour/ndnv-address-lookup/NDGISHUB_Site_Structure_Address_Points.gpkg \
  --layer Structures_NG911 \
  --verify-against <(git show 3914a49:public/911-addresses.parquet)   # use a real temp file
# All nine base columns must be "identical in order". Do not continue until they are.

# 5c. build from the new download (note the layer was renamed in the 2026 export)
python3 scripts/build-911-addresses.py <new>.gpkg --layer DBO_SiteStructureAddressPoints

# 5d. diff the street tokens against the previous file and eyeball every new one; the upstream
#     data has been drifting toward mixed case and spelled-out street types.

# 5e. re-point the existing WhereToVote scrape at the new row positions
python3 scripts/rekey-wheretovote-scrape.py \
  --input  ~/Box/.../where-to-vote-2026/fetch-WhereToVote/key-value-pairs.csv \
  --output ~/Box/.../where-to-vote-2026/fetch-WhereToVote/key-value-pairs-rekeyed-<date>.csv

# 5f. rebuild the joins and the derived columns
python3 scripts/step2-analyze-wheretovote.py --key-value-pairs <rekeyed>.csv --min-addresses 10
python3 scripts/step3-add-wheretovote-to-addresses.py
```

**Why 5e exists.** `key-value-pairs.csv`, `wheretovote-points.gpkg`, step 2 and step 3 all
identify an address by its **integer row position** in the Parquet. Adding addresses shifts every
position. Re-keying on `(house number, ZIP, street)` avoids a multi-day re-scrape of 431,238
addresses, and is more correct than the positional join. It matches on a *normalized* street
name: raw matching found 96.83% of addresses, normalized found 98.52%, recovering ~6,040
addresses that would otherwise have silently dropped from an official answer to an inferred one.

Addresses with no scraped answer are not broken — they get a polling place from the inferred
areas and the app labels them "Polling Places (inferred from location)".

## Step 5b — Re-check the 911 coordinator contacts

This is the number a voter calls when their address is wrong or missing, so it matters as much as
the polling places. On 2026-09-02, 18 of 55 entries were stale after 15 months.

Scrape <https://www.ndaco.org/cod/browse-by-position/#/position/911%20Coordinator> (it is
JS-rendered — use the Chrome DevTools MCP, not curl) and diff **name, phone, email AND title**
against `src/data/source-list.json`. Diffing only the first three misses real drift: two titles
were stale in 2026.

Two entries are **not** in NDACo, because they are city rather than county authorities, and must
be checked separately:

- index 9 `CITY OF BISMARCK 911` → <https://www.bismarcknd.gov/directory.aspx?did=5>
- index 10 `CITY OF GRAND FORKS 911` → <https://www.grandforksgov.com/government/city-departments/fire/staff>

**Edit in place. Never reorder or sort the file** — the Parquet's `src` column indexes it by array
position, index 43 is deliberately unused, and index 54 is deliberately out of alphabetical order.

Beware two shapes of legitimately odd data: one person can hold the role in several counties
(Sarah Britton covers Benson, Eddy, Nelson and Ramsey; Kent Roth covers Mercer and Oliver; Ben
Gates covers Steele and Traill), and some entries genuinely have a blank phone or email — verify
a blank on the page itself rather than assuming a parsing error.

## Step 6 — Validate

```bash
python3 scripts/validate-data.py
```

Errors must be zero. The four expected warnings as of 2026-09-02 are the Sioux `county_fp 85`
pair and the Porcupine coordinate.

## Step 7 — Test the running app. This is the real acceptance gate.

File checks cannot catch a wrong join; the rendered popup is the product.

```bash
pnpm install
./node_modules/.bin/vite build && ./node_modules/.bin/vite preview --port 5175
```

Test against the **production build**, not the dev server: Vite's dev server intermittently drops
the `counties`/`places` GeoJSON sources after a deep zoom, which makes the Sioux County fallback
look broken when it is not.

In dev mode only, `window.__map` is the maplibre instance — use it to `jumpTo` a coordinate and
`queryRenderedFeatures`. To click an address dot, dispatch `mousedown`/`mouseup`/`click`
`MouseEvent`s at the canvas centre after centring the map there.

### 7a. Changed data — must show the new values

Build the expectation table *before* running, then cross-check each against
`WhereToVoteDetail.aspx?Part=<smPrecinctPart>`. The 2026-09-02 set:

| Address | Expected |
|---|---|
| Mandaree 58757 (McKenzie) | includes **Mandaree Community Center** |
| West Fargo 58078 (Cass) | 16 locations incl. **Triumph West Church** |
| Wahpeton 58075 (Richland) | 7 locations incl. **Lidgerwood KC Hall** |
| Tioga 58852 (Williams) | **only Williston ARC** |
| Stanley 58784 (Mountrail) | 6 locations; **not** Stanley High School Commons Area or White Earth City Hall |
| Lisbon 58054 (Ransom) | **no Polling Places section at all** |
| Belcourt 58316 (Rolette) | 5 vote centers + Rolette County Courthouse drop box |
| Bismarck (Burleigh) | an **Early Voting** section |
| Carrington (Foster), Cooperstown (Griggs) | **no** County Dropboxes section |

### 7b. Unchanged data — the regression check

**Do the complete regression, not spot checks.** Compare the resolved polling-place *set* for
every address present in both the committed and rebuilt files, and group the differences by
county:

```python
# for each address key (num, street, zip, muni) present in both, resolve
# polling_places indexes -> location names and compare the sets; tally by county
```

Then check every county that changed against a list of counties you *expect* to have changed.
This is strictly better than the earlier advice to diff a handful of popups against the deployed
site: it is exhaustive, it works offline, and it still works after you deploy (the committed
files are the previous shipped state — `git show HEAD:public/...`).

It earns its keep. On 2026-09-02 spot checks caught Mountrail dropping from 8 polling places to
6. On 2026-09-23 the complete version flagged Burleigh (31 addresses) and Barnes (3) as
unexpected, which turned out to be a **shipped bug in step3** that was discarding 533 official
WhereToVote answers. Spot checks would not have found it.

Also compare the popup text for two or three unchanged counties against the deployed site while
it still serves the old data, as a sanity check on the rendering path.

### 7c. Also check

- Several of the newly-added addresses render, and say "inferred from location" rather than
  claiming to come from WhereToVote.
- **Sioux County**: tap inside the county → the fallback box opens with the polling place, all
  absentee/drop-box locations, the 911 coordinator and working directions links. Searching
  "Sioux County" or "Standing Rock Reservation" opens it too. Tap an address dot in a
  neighbouring county → the normal popup, with no state left over from the Sioux box.
- Both display paths: the desktop popup and the mobile `<dialog>` (emulate 360×640 and 320×480).
  Adding sections makes the app promote to the dialog more often; that is intended.
- Console has no new errors. `Unimplemented type: 4` is pre-existing and benign (PR #3).
- `./node_modules/.bin/svelte-check --tsconfig ./tsconfig.app.json` — the codebase has a standing
  195 errors from loose typing. Do not *add* to that count.
- Memory: cycle the popups and confirm the heap returns to ~40 MB after collection. Raw
  `usedJSHeapSize` readings include uncollected garbage and will look alarming; watch for
  *growth across cycles*, not the absolute peak.

## Step 8 — Record what happened

Add a dated audit file to `docs/` in the style of `2026-09-02-data-recheck.md`: every
discrepancy, the URL and method used to verify it, and the decision taken. The next person needs
to be able to diff against it instead of re-deriving everything.

## Decisions already made — do not silently re-litigate

- **Follow the official source, even when it is silent.** If WhereToVote says a county has not
  established polling places, the app shows nothing for those addresses rather than carrying
  forward the previous election's locations.
- **But prefer WhereToVote over the summary export.** Rolette is published in WhereToVote and
  missing from the export; the export's silence does not override the tool voters are sent to.
- **Never reorder `src/data/source-list.json`.** Its array positions are referenced by the
  Parquet's `src` column.
- **Build with the base environment's library versions**; verify structure, not bytes.
- **Render the state's wording verbatim.** Do not reclassify "Absentee Voting Day" events as
  "early voting", and do not paraphrase hours — a wrong summary can send someone to a closed
  building.
