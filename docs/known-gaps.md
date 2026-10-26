# Known gaps

What this app cannot tell you, and why. Read before describing its coverage to anyone.

Last reviewed 2026-10-26.

## Sioux County / Standing Rock: addresses arrived in October 2026, with gaps

Until September 2026 North Dakota's NG911 dataset had **zero** Sioux County address points, so
the app could not give a Standing Rock voter their official 911 address. The 2026-10-26 export
has **1,725** (`SOURCE = 'SIOUX COUNTY 911'`, which uses the long-reserved `src` index 43), and
they now get the ordinary popup. What is still imperfect:

- **Completeness is unknown.** 1,725 points for a county of roughly 3,900 people is plausible
  but unverified; a missing address gets nothing to tap, as in every other county (the
  county-wide fallback box was removed on 2026-10-26 so that a near-miss tap cannot be mistaken
  for an address answer). Road centerlines were not re-checked.
- **Only 1,097 of the 1,725 are official** (from WhereToVote, scraped for the first time on
  2026-10-26). 623 more are inferred, and all of those resolve to the county's single vote
  center, Sioux County Courthouse, so the inference cannot point anyone to the wrong building.
  Why 628 fall back: 467 have no answer (339 are not in WhereToVote at all, 40 make its search
  page fail, 88 unit addresses do not match even with the unit stripped); 101 unit addresses
  were answered for the base building but step2 rejects the answer because its prefix check
  includes the unit; and 60 are listed twice by WhereToVote (e.g. Horseshoe Rd, Cannon Ball;
  Red Tail Hawk Ave, Fort Yates, split across precincts 3102 and 3103), which step2 treats as
  ambiguous. 5 addresses get no polling place.
- **Three addresses are officially in Grant County.** 6240 and 6242 97th St SW and 8750 41st
  Ave SW are Sioux 911 points inside the Sioux County polygon, but WhereToVote puts them in
  Grant precinct 193101. Their popup shows Grant's polling places (official) **alongside
  Sioux's drop box and Absentee Voting Days** (chosen by `county_fp`). Fixing that means taking
  `county_fp` from WhereToVote for official addresses, a step3 change not made this close to
  the election.
- **Units appear twice.** Sioux County alone writes the unit into `ADDRESS`, so 157 addresses
  read e.g. `212 1st Ave N Unit 1 (UNIT 1)`. Cosmetic and faithful to the state's record; left
  for a reviewed recipe change.
- **Absentee Voting Days are time-filtered** (Sioux only). The address popup lists them in a
  "Vote Centers (Absentee Voting Days)" section that hides each event once it is over, judged
  in Mountain time because the county straddles the Central/Mountain line (`siouxCounty.js`,
  `SIOUX_EVENT_TIME_ZONE`). Text that cannot be parsed is shown rather than hidden. After
  October 30 the section disappears, leaving the courthouse drop box.

## Counties the Secretary of State has not finished entering

Re-check each of these on every refresh; they are expected to fill in before the election.

| Gap | Status 2026-10-26 |
|---|---|
| **Foster County drop box** | **Still missing** on 2026-10-26, eight days before the election. |
| Ransom County polling places | **Closed** — established; all 2,790 addresses now have a polling place. |
| Ransom County drop box | **Closed** — Ransom County Courthouse. |
| Griggs County drop box | **Closed.** |
| Ward County early voting | **Closed** — Ward County Administration Building. |
| Rolette County | **Closed** — now in the Precincts export; supplement retired. Its drop box changed to Rolette City Hall in the process. |

`scripts/precincts-supplement.json` is currently **empty**, which means `step2` will now abort
loudly on any precinct it cannot match — the guard is live rather than suppressed.

## Polling places are inferred for 13.1% of addresses

Only **86.9%** of addresses (380,802 of 438,257) have a polling place taken directly from
WhereToVote. The rest are inferred from location and the app labels them
**"Polling Places (inferred from location)"** rather than implying official provenance.

Two reasons an address is inferred:

1. It was never found in WhereToVote (about 11.5% historically — usually a street-name mismatch).
2. It is new since the scrape. Re-keying the March 2026 scrape onto the 2026-10-26 export left
   8,533 addresses without an answer; the 1,725 in Sioux County were then scraped directly,
   leaving 6,808 elsewhere.

Inference method: within each county ∩ legislative district, Voronoi areas are built around the
addresses that *were* found, and unfound addresses inherit the polling places of the area they
fall in. Simply-connected areas containing fewer than 10 attested addresses are **dropped**
rather than trusted, so some addresses get no polling place at all — **424** as of 2026-10-26
(395 on 2026-09-23, 3,681 on 2026-09-02). The October increase is 22 Minot Air Force Base
addresses, which WhereToVote does not know at all: two nearby attested addresses disappeared
upstream, the area around them fell below the threshold and was dropped, plus 5 in Sioux County.

## Two hand-imputed precincts

`scripts/step2-analyze-wheretovote.py` maps two precincts that WhereToVote returns but the
polling-place file does not list:

- `083204 → 083205` — county 08, district 32 has precincts 01, 02, 03, 05 but no 04, and all the
  others share the same polling locations.
- `320902 → 320901` — county 32, district 09 has only precinct 01.

## Location coordinates

- **`Porcupine Local District Buidling`** (Sioux County; the misspelling is the state's) is
  located to **street level, not address level**. No geocoder resolves house number 3457 on Paha
  Yamni Loop: the Census and Nominatim geocoders find nothing, OSM has no such way, and Google
  resolves only the street. The shipped coordinate is a point on Paha Yamni Loop in Porcupine
  beside the large community building at the centre of the loop — gymnasium-scale, metal-clad
  with a painted hills mural, a solar array and a large parking lot, and the only institutional
  structure among roughly twenty houses. Taken from the Google Street View camera position
  (Sep 2024 capture; the minimap confirms "Porcupine"). No sign is legible from any available
  angle, so the building's identity is inferred from context rather than confirmed.
  **Two wrong answers to avoid**, both of which a voter searching for themselves would hit:
  a Google name search returns a building in Porcupine, **South Dakota**, 350 km away; and the
  MapQuest entry for "Porcupine Local District" (`46.040379, -100.922115`, `streetAddress: null`)
  sits 24.1 km away in **Selfridge**, 256 m from the Selfridge Senior Center. The cause of the
  latter is that ZIP 58568's postal locality is Selfridge and Porcupine shares it — Google labels
  this very street "Paha Yamni Loop, Selfridge, North Dakota". Any geocoder that resolves the ZIP
  to a city lands in Selfridge. To confirm the building properly, ask the Sioux County auditor,
  (701) 854-3481.
- **Veterans Memorial Building**, Cannon Ball, is street-level rather than building-level: the
  coordinate sits on Horseshoe Rd in the right village, but house number 440 could not be
  pinpointed.
- **Solen Fire Hall**'s coordinate comes from the address interpolation; Google labels a "Fire
  Department" on Leach St about 90 m north-west. Either lands in the village.
- **Coordinates are keyed by location *name* alone.** Two locations sharing a name but not an
  address would give one of them wrong directions. No collisions exist today and
  `validate-data.py` fails if any appear. The `*-locations.json` files intentionally retain keys
  for retired locations as a cache of manually verified coordinates, which is what let twelve
  renamed locations keep their verification in September 2026.

## Address text quirks, carried through deliberately

The app shows the state's data as-is rather than cleaning it, so that what a voter copies matches
the official record.

- **Ordinal and name casing.** The upstream data has been drifting from all-caps toward mixed
  case, and the casing rule (faithful to the original recipe) turns mixed-case input into forms
  like `28Th Ave` and `Mcdougall` rather than `28th Ave` and `McDougall`. Roughly 1,500 addresses
  are affected, up from a handful. Cosmetic, and fixing it would change thousands of existing
  addresses at once — worth doing as its own reviewed change, not folded into a data refresh.
- One address has **no street name at all** (`ADDRESS` is just a number).
- `unit` contains the literal string `<Null>` on 6 rows, and values with trailing spaces.
- One `zip` is the malformed 4-digit `5885`; 16 addresses have no ZIP.
- `dropboxes.csv` has a garbled `state` column (one row reads `No`). The app never reads it.
- Some drop-box hours fields are empty, rendering a blank line.

## Map labels are limited to the 0-255 glyph range

The app bundles only `0-255.pbf` per font (Noto Sans Bold / Regular / Italic). Any character
above U+00FF makes maplibre request a glyph range that is not there, it 404s, and **maplibre
drops the entire label** rather than rendering the characters it does have.

**Twin Buttes is invisible on the map.** `places.geojson` names it
`Twin Buttes / cuuk gaamaa[glottal]uush / Tiiru[apostrophe]pa Pshii Woonis` (real text uses
U+0294 LATIN LETTER GLOTTAL STOP, needing range 512-767, and U+2019 RIGHT SINGLE QUOTATION MARK,
needing 8192-8447). The accented vowels are inside 0-255 and fine; those two are not, so the
label never draws -- verified on the deployed site at z12.2 centred on the community, while
Mandaree and Spotted Horn render normally.

This matters more than a typical label bug: Twin Buttes is a Fort Berthold community with its
own polling place (Twin Buttes Community Center), and the missing text is its Mandan/Hidatsa
name. It is **pre-existing** (introduced with `places.geojson` in 2025) and affects no voting
information, so it did not block the September 2026 releases.

Fixing it properly means shipping the two glyph ranges for Noto Sans Regular, which needs a
fontnik-style SDF glyph build that is not set up in this repo. **Do not "fix" it by substituting
ASCII lookalikes** -- the apostrophe in that name may be orthographically meaningful rather than
decorative punctuation, and that is a decision for the community, not for us.

`scripts/validate-data.py` now warns about any label character the shipped ranges cannot render,
and **errors** for `text-field` literals in `map-style.json` (which are ours to control).

## Coordinates are lossily compressed

`lon`/`lat` are float32 with low mantissa bits cleared: about **3 m of longitude and 5 m of
latitude** of error, chosen to let `BYTE_STREAM_SPLIT` + zstd compress. Fine for identifying a
building on a map; not survey data.

## Not offline-capable

Everything except satellite imagery loads at startup, so the app works on a spotty connection —
but satellite tiles come from Google at run time and the imagery for the whole state is ~29 GB,
so it can never be bundled. With no network the background is simply blurred.

## Served but unused (~4.4 MB)

`public/` ships files the browser never fetches: `legislative-districts.geojson`,
`polling-places.parquet`, and `fonts/Noto Sans Italic/`. Two more —
`counties-exact.gpkg` (2.0 MB) and `legislative-districts-exact.gpkg` (1.8 MB) — are genuine
build-time inputs for steps 2 and 3 and should **move out of `public/`** rather than be deleted.
Doing so would take `dist` from 18 MB to about 14 MB, closer to the ~10 MB target.

## Minor

- The drop-box section renders its hours through `{@html}` after inserting a `<br>`. The text is
  state-controlled rather than user-controlled, but it is a needless injection surface; the newer
  early-voting and Sioux sections render as plain text instead.
- The app promotes from an inline popup to a modal dialog when the content would overflow the
  viewport. Adding the Early Voting section makes that happen more often — intended, but it means
  the modal path is now the common one on phones.
