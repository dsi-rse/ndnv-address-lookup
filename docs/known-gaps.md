# Known gaps

What this app cannot tell you, and why. Read before describing its coverage to anyone.

Last reviewed 2026-09-23.

## Sioux County / Standing Rock has no state 911 data at all

North Dakota's NG911 dataset contains **zero of 435,480 address points and zero of 175,283 road
centerlines** for Sioux County. Not a processing loss on our side — the state does not have it.
`msag` has no rows for Fort Yates, Cannon Ball, Selfridge, Porcupine or Twin Buttes.

So the app **cannot give a Standing Rock voter their official 911 address**, which is the app's
primary purpose. That has been true since the first release (it is noted in
`uchicago-dsi/north_dakota_native_vote#35`).

Mitigated as of 2026-09-02 by the Sioux County fallback: tapping the county, or searching "Sioux
County" or "Standing Rock Reservation", opens a box with everything that *is* known — the polling
place, all drop-box and absentee-voting-day locations, the 911 coordinator to call, and driving
directions. It explains that the gap is in the state's data, not the voter's registration.

**Worth pursuing:** an address source from the Standing Rock Sioux Tribe or the BIA. That would
turn the fallback into a real address lookup.

## Counties the Secretary of State has not finished entering

Re-check each of these on every refresh; they are expected to fill in before the election.

| Gap | Status 2026-09-23 |
|---|---|
| **Foster County drop box** | **Still missing.** The only remaining county gap. |
| Ransom County polling places | **Closed** — established; all 2,790 addresses now have a polling place. |
| Ransom County drop box | **Closed** — Ransom County Courthouse. |
| Griggs County drop box | **Closed.** |
| Ward County early voting | **Closed** — Ward County Administration Building. |
| Rolette County | **Closed** — now in the Precincts export; supplement retired. Its drop box changed to Rolette City Hall in the process. |

`scripts/precincts-supplement.json` is currently **empty**, which means `step2` will now abort
loudly on any precinct it cannot match — the guard is live rather than suppressed.

## Polling places are inferred for 13.0% of addresses

Only **87.0%** of addresses (379,761 of 436,314) have a polling place taken directly from
WhereToVote. The rest are inferred from location and the app labels them
**"Polling Places (inferred from location)"** rather than implying official provenance.

Two reasons an address is inferred:

1. It was never found in WhereToVote (about 11.5% historically — usually a street-name mismatch).
2. It is new since the scrape. 4,242 addresses were added between April 2025 and September 2026,
   and re-keying the old scrape onto them left 6,135 without a scraped answer.

Inference method: within each county ∩ legislative district, Voronoi areas are built around the
addresses that *were* found, and unfound addresses inherit the polling places of the area they
fall in. Simply-connected areas containing fewer than 10 attested addresses are **dropped**
rather than trusted, so some addresses get no polling place at all — **395** as of 2026-09-23,
down from 3,681, after Ransom was resolved and after a step3 bug was fixed that had been
discarding 533 addresses' official answers along with the dropped polygons.

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

## The Sioux County "tap here" hint only appears at zoom 12+

`sioux-fallback-label` is declared with `minzoom: 7`, but `reservation-names` ("Standing Rock")
wins the symbol-collision contest below zoom 12, so the hint does not actually draw until
`reservation-names` stops at its `maxzoom` of 12. Measured with `queryRenderedFeatures`: 0
rendered at z7/z9/z11, then 3/4/6 at z12/z13/z14.

In practice both realistic paths still work -- searching "Sioux County" or "Standing Rock
Reservation" opens the box directly, and a voter zooming in to look for address dots has to pass
zoom 11 anyway -- so this was left alone rather than changing collision behaviour just before an
election. Worth revisiting afterwards.

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
