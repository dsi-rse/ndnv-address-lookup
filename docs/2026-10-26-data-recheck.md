# Data re-check, 2026-10-26

Final pre-election checkpoint (see `recheck-runbook.md`), eight days before the **November 3,
2026** general election. The previous check was 2026-09-23.

Election id is still **`eid=348`** (re-derived from the "2026 General Election Statewide Polling
Places and Precincts" link on the Secretary of State's current/past elections page).

## Headline: Sioux County has 911 addresses for the first time

The cheap probe that had returned 0 on every previous run returned **1,725**. The state's NG911
layer now has Sioux County address points (`SOURCE = 'SIOUX COUNTY 911'`, `DiscrpAgID =
intrado.com`, `DateUpdate` 2026-09-03 … 2026-10-23, so they were loaded after the 2026-09-23
check with back-dated timestamps). By MSAG community: Fort Yates 1,001, Selfridge 265, Cannon
Ball 228, Solen 94, Porcupine 52, and 85 in townships.

Decision (by the project lead, this run): **ship them**, with the ordinary address popup
including the drop box, plus a Sioux-only section at the end for the Absentee Voting Days that
shows only events that are still current or upcoming. Details under "App changes".

`source-list.json` index 43 (`SIOUX COUNTY 911`) had been reserved for exactly this; the
coordinator (Angela Eagle, 701-854-3481, aeagle@nd.gov) still matches NDACo.

## Changes from the Secretary of State

| Change | Addresses affected | Verified at |
|---|---|---|
| **Sheridan:** `McClusky City Hall, 117 B Ave East` → **`McClusky Ambulance Bay, 311 Main Str. South`** (the county's only site) | 953 (+1 McLean-sourced address in a Sheridan precinct) | `WhereToVoteDetail.aspx?Part=42140105` lists McClusky Ambulance Bay |
| **Williams:** Ernie French Center moved from precinct 01-24 to precinct 23-22 | 580 gained it, 10 lost it | `Part=53012401` lists ARC + Fairgrounds only; `Part=53232201` lists Ernie French Center + ARC + Fairgrounds |
| **Traill:** drop-box text typo "brining" → "bringing" | — | export |

The `nodups` row for McClusky kept its position, so `polling_places` indexes were not disturbed.
**Foster County still has no drop box** — the only county gap, now presumably permanent for this
election. `precincts-supplement.json` remains empty.

## 911 addresses rebuilt

The layer was being edited the morning of this run (`dataLastEditDate` 2026-10-26 10:46 UTC).
436,314 → **438,257** (+1,943): Sioux +1,725, everywhere else +218 net (largest: Ward +49,
Morton +25, Richland +16, Mountrail +14; McKenzie −11).

- Hub GeoPackage export generated fresh (`gpkg_contents.last_change` 2026-10-26T15:10Z) with
  438,257 features — matches the live service count.
- Blocking regression against the April-2025 snapshot: **9/9 base columns identical in order,
  206 row groups.** (A different April-2025 export of 431,212 features also exists on the
  storage drive and fails every column; it is the wrong input, not a recipe problem.)
- Additionally, 99.91% of the 2026-09-23 shipped rows (435,925 of 436,314) are reproduced
  exactly by the new build; the 389 that are not are upstream edits.
- **208 row groups** (was 206): Sioux County's census tracts are new.
- Structure identical: column order and types, per-column encodings, zstd, format 2.6,
  pyarrow 25.0.0.
- New street tokens: 123, all Sioux County except `Cruise Missile Ln` (Ward). They are Lakota
  street names (Mniconju, Sisitonwan, Thasiyagmunka, Wiyohepeyata, Cant'E …), letter-suffixed
  rural grid numbers (`69M St SW`, `95A St SW`), and unit text — see below. No new casing
  problems.
- Sioux County alone writes the unit into `ADDRESS` (`411 STANDING ROCK AVE UNIT 5656`) as well
  as into `Unit`, so 157 Sioux addresses render as e.g. `212 1st Ave N Unit 1 (UNIT 1)`. Left
  as-is (faithful to the state's record; changing the recipe would break the regression test).

### Re-keying and the first Sioux scrape

The original scrape re-keyed onto the new file at **98.05%** (429,724 of 438,257); 8,533
addresses had no answer, 1,725 of them in Sioux County. With no attested Sioux points the
inference has nothing to work from, so Sioux was scraped directly:
`step0-batch` on a subset Parquet (index preserved), 4 in parallel.

- First pass: 1,151 answered. Retry of network errors and of unit addresses with the unit
  stripped: +107. **1,258 answered** in total.
- After step2's own checks, **1,097 Sioux addresses are official**, 623 inferred (all to Sioux
  County Courthouse, the single vote center), 5 none. The 161-answer gap is 101 unit addresses
  whose answer is for the base building (step2's prefix check includes the unit) and 60 that
  WhereToVote lists twice.
- WhereToVote puts **3 Sioux-sourced points in Grant County** (precinct 193101): 6240 and 6242
  97th St SW, 8750 41st Ave SW. Shipped as WhereToVote says (Grant polling places), but their
  popup also shows Sioux's drop box and Absentee Voting Days. Written up in `known-gaps.md`.
- Merged file: `where-to-vote-2026/fetch-WhereToVote/key-value-pairs-rekeyed-2026-10-26-with-sioux.csv`
  (Sioux rows alone: `sioux-2026-10-26.csv`). The previous `wheretovote-*.gpkg` and
  `missing-points.gpkg` were overwritten by step2 as designed.

## Complete polling-assignment regression

All 432,183 addresses present in both versions were compared by resolved location-name set.
**1,566 changed:**

| County (911 source) | Changed | What | Expected? |
|---|---|---|---|
| Sheridan | 953 | McClusky City Hall → McClusky Ambulance Bay | yes |
| McLean | 1 | same (an address in a Sheridan precinct) | yes |
| Williams | 590 | 580 gained Ernie French Center, 10 lost it | yes |
| **Ward** | **22** | **lost every polling place** | investigated |

The 22 Ward addresses are all on **Minot Air Force Base** (Alert Ave, Deterrence Dr, Fighter
Rd, Flightline Dr), were never official, and WhereToVote does not know those streets at all
(checked directly). Two attested addresses nearby disappeared upstream, the inferred area fell
below the 10-address threshold and was dropped. That is the rule working as designed ("follow
the official source, even when it is silent"); recorded rather than overridden.

No `in_wheretovote` value flipped for any address present in both versions.

| | 2026-09-23 | 2026-10-26 |
|---|---|---|
| Addresses | 436,314 | 438,257 |
| Official (from WhereToVote) | 379,761 (87.0%) | 380,802 (86.9%) |
| No polling place at all | 395 | 424 (419 outside Sioux) |

## 911 coordinator contacts

All 53 county entries match NDACo on name, phone, email and title (Foster still "Position
Vacant", stored as `(position vacant)`). Bismarck CenCom (Mike Dannenfelzer, 701-255-5200) and
Grand Forks Fire (701-746-2566, fire_admin@grandforksgov.com) unchanged.

## Coordinates

| Location | Coordinate | Verification |
|---|---|---|
| McClusky Ambulance Bay, 311 Main St S, McClusky | 47.4835601, -100.442422 | Google echoes **311 Main St S, McClusky**; Street View shows the building signed for the ambulance service. Census geocode was 29 m away. Google's "Mc Clusky Ambulance Center" listing is marked permanently closed and sits ~250 m north (the old site) — not used. |

## App changes

All in `src/lib/` plus one map label; `svelte-check` went from 195 to **192** errors (annotating
`dropboxes` removed three).

- **Sioux addresses get the normal popup.** For `county_fp` 85 only:
  - *County Dropboxes* shows the real drop box — Absentee Voting Day rows are moved out, and the
    bare "Sioux County Courthouse" row with no hours (a duplicate at the same address) is
    dropped.
  - *Early Voting* omits Absentee Voting Day rows (all five of Sioux's), so it does not appear.
  - New last section **"Vote Centers (Absentee Voting Days)"**: the events from both tabs,
    de-duplicated, soonest first, rendered verbatim, and **hidden once over**.
- **Time filter** (`siouxCounty.js`): parses "October 30th 2026 5pm-7pm" style text; an event
  counts as over once the wall clock in **America/Denver** passes its end time. Sioux County
  straddles the Central/Mountain line (Fort Yates is Central; west of ND 31 is Mountain), so
  Mountain time is the later of the two possible closings — an event can linger an hour, never
  vanish early. Unparseable text is always shown. Same filter in the county-wide box.
- **County-wide box and label reworded**: no longer claims there are no addresses
  ("Tap for Sioux County voting information"; lead says addresses arrived in October 2026).
  It stays reachable by tapping between dots and by searching "Sioux County" / "Standing Rock
  Reservation".
- `step0-batch-fetch-WhereToVote-districts.py` pointed at the pre-rename
  `scripts/fetch-WhereToVote-districts.py`; fixed.

**Terminology caveat:** the county-wide box still says Sioux "uses vote centers … and has only
one" (the courthouse, election day), while the new popup section calls the Absentee Voting Day
sites "Vote Centers". Both follow instructions given; worth reconciling if anyone finds it
confusing.

## Verification performed

On the production build (`vite build && vite preview`) with the Chrome DevTools MCP:

- 10 Agency Ave, Fort Yates: Sioux coordinator, Sioux County Courthouse (from WhereToVote),
  courthouse drop box only, all five Absentee Voting Days with working directions links.
- Clock faked via `initScript`: at 2026-10-28 18:30 MDT, Porcupine (ends 19:00) still shown,
  Oct 26/27 hidden; at 19:00 MDT Porcupine hidden; on Nov 1 the section is gone from the popup
  and from the county-wide box, leaving the drop box.
- Sioux inferred address labelled "inferred from location"; unit address shows the duplicated
  unit; the Grant-precinct address shows Grant polling places as described above.
- McClusky shows Ambulance Bay; Williams 14111 Willow Dr (district 23) includes Ernie French
  Center; 2801 Broadway N, Fargo still shows all 16 official locations; Foster has no drop box.
- Search "Sioux County" opens the box (12 links); tapping between dots after closing a popup
  opens it with no state left over.
- Mobile `<dialog>` at 360×640 and 320×480: no horizontal overflow.
- No console errors or warnings; no failed requests; only the `0-255` glyph ranges requested.
- Memory: after cycling 12 popups across four regions and forcing GC, 26 MB on a fresh page vs
  25 MB for a build of the previous commit under the identical procedure; no growth across
  repeated cycles.
- `validate-data.py`: 0 errors, 2 warnings (Twin Buttes glyphs; the Sioux `county_fp 85`
  warnings are gone). `dist` 18 MB.

## Process notes

- **The Box folder was lost in the 2026-09-26 machine move** and had to be restored by hand
  before steps 2/3 could run. The TIGER tract file (`~/Downloads/tl_2024_38_tract.zip`) was
  lost too and was re-downloaded from the Census Bureau.
- **`WhereToVoteDetail.aspx` now needs a session**: a cold request redirects to "This site is
  no longer active". After one search through the form, `Part=…&tab=&ptlPKID=&ptlhPKID=`
  works. Runbook updated.
- The Hub `resultUrl` now redirects to blob storage; `curl -L` is needed.
