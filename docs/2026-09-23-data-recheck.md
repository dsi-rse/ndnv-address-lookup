# Data re-check, 2026-09-23

Second of the three pre-election checkpoints (see `recheck-runbook.md`), run the day before
absentee voting opens on **September 24, 2026**. The previous check was 2026-09-02, shipped as
PR #35 and confirmed live on `myaddress.ndnativevote.org` during this run.

Election id is still **`eid=348`**; the June primary's links have been removed from the
Secretary of State's current/past elections page entirely.

## Headline: the Secretary of State filled in almost every gap

Three of the four county gaps carried in `scripts/precincts-supplement.json` and
`known-gaps.md` have closed, and the supplement is now **empty**.

| Gap as of 2026-09-02 | Status now |
|---|---|
| **Ransom County** — "not established at this time by the county" | **Established.** `WhereToVoteDetail.aspx?Part=37240103` now returns the "2026 General Election" heading with EXPO (Lisbon) and City Auditors Office (Enderlin), 9:00AM–7:00PM, plus a courthouse drop box. All **2,790** Ransom addresses went from *no polling place* to having one. |
| **Rolette County** — published in WhereToVote but missing from the export | **In the export.** `step1` printed `SKIP supplement`, exactly as designed. |
| **Griggs County drop box** — dropped after the primary | **Restored** (Griggs County Courthouse). |
| **Ward County early voting** — absent from `eid=348` | **Restored** (Ward County Administration Building). |
| **Foster County drop box** | **Still missing.** The only remaining county gap. |

Retiring the Rolette supplement was not a no-op: the export's drop box is
**Rolette City Hall, 302 Main St ("Utility Dropbox")**, not the
Rolette County Courthouse at 102 2nd St NE that the supplement carried from WhereToVote in
September. WhereToVote now agrees with the export. Carrying the supplement forward would have
shipped a stale drop-box location.

## Other changes from the Secretary of State

- **Williams County reversed its consolidation.** In September it had collapsed to Williston ARC
  alone; it is now back to multiple sites (Williams County Fairgrounds, Ernie French Center,
  Grenora City Hall, Ray City Hall, Tioga Community Center, Wildrose Fire Hall). **16,493**
  addresses affected — the largest single change. Verified at `Part=53012101`.
- **Mountrail County:** `New Town Civic Center Auditorium, 103 Soo Place` → **`New Town The
  Venue, 235 Main St`**, and Ross Community Building's address corrected `300 Main St` →
  `203 Main St`. 4,986 addresses affected. Verified at `Part=31020101`. New Town is on Fort
  Berthold.
- **Rolette:** `St John Senior Center` → `St. John Senior Center` (punctuation only, but it is a
  coordinate lookup key — see below).
- **New drop boxes:** Ramsey County Courthouse, Ransom County Courthouse, Griggs County
  Courthouse, Rolette City Hall. **Removed:** the bare duplicate Adams County Courthouse row.
- **Burleigh early voting** gained real dates: Oct 22 – Nov 2, 2026.
- **Cavalier County's drop-box text was fixed by the state** from "Tuesday, **June 9th**, 2026"
  to "Tuesday, November 3rd, 2026". We shipped the June text for three weeks — see
  "What the process missed" below.

## 911 addresses rebuilt

The GIS Hub layer was edited 2026-09-21. 435,480 → **436,314** (+834).

- Blocking recipe regression against the April-2025 snapshot: all nine base columns identical
  and in order, 206 row groups. Passed before touching the new export.
- Only **5** new street tokens (`Hoberg`, `Themis`, `Berning`, `Fairchild`, `Wollenzien`) — all
  ordinary names, no new casing or acronym cases. No new `SOURCE` values.
- The existing WhereToVote scrape was re-keyed onto the new row positions: **98.50%** matched.
- Parquet structure identical to the shipped file: same column order, types, per-column
  encodings, compression and 206 one-per-census-tract row groups.

## 911 coordinator contacts

All 53 county entries still match the NDACo directory on name, phone, email **and** title — no
changes. The two city entries not covered by NDACo were re-verified directly and are unchanged:
Bismarck CenCom (Mike Dannenfelzer, 701-255-5200) and Grand Forks Fire
(701-746-2566, fire_admin@grandforksgov.com).

## Coverage

| | 2026-09-02 | 2026-09-23 |
|---|---|---|
| Addresses | 435,480 | 436,314 |
| Official (from WhereToVote) | 376,852 (86.5%) | 379,761 (87.0%) |
| **No polling place at all** | **3,681** | **395** |

## What the process missed — three fixes

The user asked for the process to be re-thought rather than just re-run. Three real problems
surfaced, one of them a shipped bug. All three now have automated guards in
`scripts/validate-data.py`.

### 1. Official answers were being silently discarded (shipped bug)

`step3-add-wheretovote-to-addresses.py` filled `polling_places` **only from the inferred
polygons**. It computed each address's own WhereToVote answer, used it for a consistency check,
and then threw it away. Because `remove_small_polling_area_components()` deliberately drops
simply-connected polygons with fewer than `--min-addresses` points, any address inside a dropped
polygon lost its polling place — *even when WhereToVote had answered it directly*.

**533 addresses** were affected, all with `in_wheretovote = True`. Most were in Fargo; e.g.
`2801 Broadway N, Fargo 58102`, for which WhereToVote lists all 16 Cass County vote centers, and
the app showed nothing.

Dropping a shaky *inference* is correct; dropping the state's own answer is not. Fixed by
filling from the polygons first and then letting the points override. The pre-existing
disagreement check already proves the two sources agree wherever they overlap, so the change is
purely additive. This is why "no polling place at all" fell to 395 rather than ~928.

`validate-data.py` now **errors** if any `in_wheretovote = True` address has an empty
`polling_places`.

### 2. Stale election dates in free text went unnoticed

Cavalier County's drop-box row still told voters their ballot was due "**June 9th**, 2026" — the
primary date — and we shipped it for three weeks. Nothing checked the state's free text for
dates from the wrong election.

`validate-data.py` now parses every month-day reference in `polling_hours`,
`early_voting_times` and `comments`, and **errors** on any date outside the
2026-09-24 … 2026-11-03 window. (The naive version of this check produced false positives on the
word "may" and on Ward's legitimate "September 24th" absentee-open date, so it parses real dates
rather than matching month names.)

### 3. A location can move while keeping its name

`geocode-polling-places.py` is incremental **by name**, so when Ross Community Building moved
from 300 Main St to 203 Main St it kept its old coordinate silently. Caught here only because
the address diff was run by hand.

`validate-data.py` now compares each location's address against the committed copy
(`git show HEAD:public/...`) and **warns** when a name is unchanged but its address is not.

## Coordinates

New or re-verified this cycle:

| Location | Coordinate | Verification |
|---|---|---|
| New Town The Venue, 235 Main St, New Town | 47.979232, -102.490418 | Google labels **235** at that point on Main St beside the Tribal Public Works Department |
| Ross Community Building, 203 Main St, Ross | 48.312879, -102.543966 | re-geocoded after the move; 90 m from the old point |
| Ransom County Courthouse (Drop Box), Lisbon | 46.441801, -97.684126 | 276 m from the hand-verified EXPO in Lisbon |
| Rolette City Hall (Drop Box), Rolette | 48.661989, -99.844824 | 72 m from the hand-verified WWI Memorial Building in Rolette |
| St. John Senior Center (renamed) | unchanged | fresh Census geocode was **396 m** off; satellite shows the long-standing hand-verified point on Foussard Ave SW among the 200-block numbers, so the verified coordinate was kept |
| Ramsey County Courthouse (Drop Box) | unchanged | same address as the hand-verified Memorial Building (0 m) |
| Ward Admin Building (early voting) | unchanged | matched to the verified polling-place coordinate |

A Nominatim town-centroid sanity check flagged Rolette City Hall as "8.9 km from Rolette"; that
was a bad reference node, not a bad coordinate. Cross-checking against a **hand-verified location
in the same town** is the reliable test.

## Verification performed

- `build-911-addresses.py --verify-against` the April-2025 snapshot: 9/9 base columns identical
  in order.
- `validate-data.py`: 0 errors, 3 warnings (the two known Sioux `county_fp 85` notes, plus the
  new Ross address-change warning, which is expected and was acted on).
- **Complete** polling-assignment regression across all 356,991 addresses present in both
  versions — not spot checks. 30,815 changed, in Williams, Rolette, Mountrail and Ransom as
  expected, plus Burleigh (31) and Barnes (3), which is what exposed bug #1 above.
- App driven on the production build with the Chrome DevTools MCP: Ransom now shows polling
  places and a drop box; Rolette shows 5 vote centers and the City Hall drop box; Williams shows
  6 locations; Mountrail shows New Town The Venue; Ward shows early voting; Griggs shows a drop
  box; Foster still shows none; Pembina and Adams unchanged; the previously-blank Fargo address
  now shows all 16 official locations; the Sioux County fallback opens with 11 working links.
- `svelte-check` unchanged at the standing 195 errors. `vite build` clean, `dist` 18 MB.
- Production confirmed to be serving the 2026-09-02 data (435,480 rows), i.e. PR #35 deployed.

## For the final (late-October) check

- **Foster County drop box** is the one remaining gap.
- **Past-dated events.** By late October several of Sioux County's "Absentee Voting Day" events
  (Oct 26–30) and other counties' early-voting windows will have passed or be passing. The app
  renders the state's text verbatim with no notion of "past", so a voter could read an expired
  date as current. Worth deciding before the final refresh whether to de-emphasise elapsed
  entries. This is the one time-sensitivity the app does not currently handle.
- `src/lib/siouxCounty.js` hardcodes `eid=348` in `SOS_PRECINCTS_URL`, a second copy of the
  election id besides `step1`'s default. Both must change together.
