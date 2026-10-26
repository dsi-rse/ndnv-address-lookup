<script>
  import { onDestroy, tick } from 'svelte';
  import { getMapContext, GeoJSON, CircleLayer, Popup } from 'svelte-maplibre';

  import AddressDetailsContent from './AddressDetailsContent.svelte';
  import { getDirectionsUrl } from './directions.js';
  import {
    SIOUX_COUNTY_FP,
    absenteeVotingDayEnd,
    absenteeVotingDayHasEnded,
    dedupeLocations,
    isAbsenteeVotingDay,
  } from './siouxCounty.js';
  import sourceList from "../data/source-list.json";
  import { parquetMetadata, parquetRead } from "hyparquet";
  import { compressors } from "hyparquet-compressors";

  const MIN_ZOOM_FOR_POINTS = 11;

  let regions = [];
  let visibleIndexes = [];
  let forEachIndex = {};
  let parquetFile = null;
  const url = new URL("/911-addresses.parquet", import.meta.url).href;
  const pollingPlacesUrl = new URL("/polling-places-nodups.csv", import.meta.url).href;
  const dropboxesUrl = new URL("/dropboxes.csv", import.meta.url).href;
  const pollingPlaceLocationsUrl = new URL("/polling-places-locations.json", import.meta.url).href;
  const dropboxLocationsUrl = new URL("/dropboxes-locations.json", import.meta.url).href;
  const earlyVotingUrl = new URL("/early-voting.csv", import.meta.url).href;
  const earlyVotingLocationsUrl = new URL("/early-voting-locations.json", import.meta.url).href;
  let pollingPlaces = [];
  /** @type {any[]} */
  let dropboxes = [];
  /** @type {any[]} */
  let earlyVoting = [];
  let pollingPlaceLocations = {};
  let dropboxLocations = {};
  /** @type {Record<string, number[]>} */
  let earlyVotingLocations = {};

  function parseCsv(text) {
    let rows = [];
    let row = [];
    let field = "";
    let inQuotes = false;

    for (let i = 0;  i < text.length;  i++) {
      const char = text[i];
      const next = text[i + 1];

      if (inQuotes) {
        if (char == '"'  &&  next == '"') {
          field += '"';
          i += 1;
        }
        else if (char == '"') {
          inQuotes = false;
        }
        else {
          field += char;
        }
      }
      else if (char == '"') {
        inQuotes = true;
      }
      else if (char == ",") {
        row.push(field);
        field = "";
      }
      else if (char == "\n") {
        row.push(field);
        rows.push(row);
        row = [];
        field = "";
      }
      else if (char != "\r") {
        field += char;
      }
    }

    if (field != ""  ||  row.length != 0) {
      row.push(field);
      rows.push(row);
    }

    const headers = rows[0] ?? [];
    return rows.slice(1).map(values =>
      Object.fromEntries(headers.map((header, index) => [header, values[index] ?? ""]))
    );
  }

  function hasNewIndexes(newVisibleIndexes) {
    if (newVisibleIndexes.length > visibleIndexes.length) {
      return true;
    }
    let oldi = 0;
    let newi = 0;
    while (oldi < visibleIndexes.length  &&  newi < newVisibleIndexes.length) {
      if (visibleIndexes[oldi] < newVisibleIndexes[newi]) {
        oldi += 1;
      }
      else if (visibleIndexes[oldi] == newVisibleIndexes[newi]) {
        oldi += 1;
        newi += 1;
      }
      else {
        return true;
      }
    }
    return newi < newVisibleIndexes.length;
  }

  async function readFromParquet(index) {
    return new Promise((onComplete) =>
      parquetRead({
        file: parquetFile,
        //          0        1        2       3       4      5      6      7           8      9      10                11               12
        columns: ["num", "street", "unit", "muni", "msag", "zip", "src", "district", "lon", "lat", "in_wheretovote", "polling_places", "county_fp"],
        rowStart: regions[index].start,
        rowEnd: regions[index].stop,
        compressors,
        onComplete,
      })
    ).then(data => {
      forEachIndex[index.toString()] = data.map(row => ({
        type: "Feature",
        geometry: {
          type: "Point",
          coordinates: [row[8], row[9]],
        },
        properties: {
          num: row[0],
          street: row[1],
          unit: row[2],
          muni: row[3],
          msag: row[4],
          zip: row[5],
          src: row[6],
          district: row[7],
          lon: row[8],
          lat: row[9],
          in_wheretovote: row[10],
          polling_places: row[11],
          county_fp: row[12],
        },
      }));
    });
  }

  const { map, loaded } = $derived(getMapContext());
  $effect(() => {
    if (loaded) {
      map.on("zoom", handleMove);
      map.on("move", handleMove);
    }
  });

  function reloadSource() {
    if (loaded) {
      map.getSource("addresses").setData({
        type: "FeatureCollection",
        features: visibleIndexes.map(i => forEachIndex[i] ?? []).flat(),
      });
    }
  }

  async function handleMove(event) {
    if (event.target.getZoom() >= MIN_ZOOM_FOR_POINTS) {
      const bounds = event.target.getBounds();
      const west = bounds.getWest();
      const east = bounds.getEast();
      const south = bounds.getSouth();
      const north = bounds.getNorth();

      let newVisibleIndexes = [];
      for (let i = 0;  i < regions.length;  i++) {
        const r = regions[i];
        if (r.east >= west  &&  r.west <= east  &&  r.north >= south  &&  r.south <= north) {
          newVisibleIndexes.push(i);
        }
      }

      if (hasNewIndexes(newVisibleIndexes)  &&  parquetFile !== null) {
        visibleIndexes = newVisibleIndexes;

        for (const index in forEachIndex) {
          if (!(Number(index) in visibleIndexes)) {
            delete forEachIndex[index];
          }
        }

        let promises = [];
        for (const index of visibleIndexes) {
          if (!(index.toString() in forEachIndex)) {
            promises.push(readFromParquet(index));
          }
        }
        Promise.all(promises).then(reloadSource).catch(reloadSource);
      }
    }
  }

  fetch(url).then(async response => {
    if (!response.ok) {
      return;
    }
    parquetFile = await response.arrayBuffer();

    const metadata = parquetMetadata(parquetFile);

    let start = 0;
    for (const rg of metadata.row_groups) {
      let lonStats = rg.columns.filter(x => x.meta_data.path_in_schema[0] == "lon")[0].meta_data.statistics;
      let latStats = rg.columns.filter(x => x.meta_data.path_in_schema[0] == "lat")[0].meta_data.statistics;

      const stop = start + Number(rg.num_rows);
      regions.push({
        start: start,
        stop: stop,
        west: lonStats.min_value,
        east: lonStats.max_value,
        south: latStats.min_value,
        north: latStats.max_value,
      });
      start = stop;
    }
  });

  fetch(pollingPlacesUrl).then(async response => {
    if (!response.ok) {
      return;
    }
    pollingPlaces = parseCsv(await response.text());
  });

  fetch(dropboxesUrl).then(async response => {
    if (!response.ok) {
      return;
    }
    dropboxes = parseCsv(await response.text());
  });

  fetch(pollingPlaceLocationsUrl).then(async response => {
    if (!response.ok) {
      return;
    }
    pollingPlaceLocations = await response.json();
  });

  fetch(dropboxLocationsUrl).then(async response => {
    if (!response.ok) {
      return;
    }
    dropboxLocations = await response.json();
  });

  fetch(earlyVotingUrl).then(async response => {
    if (!response.ok) {
      return;
    }
    earlyVoting = parseCsv(await response.text());
  });

  fetch(earlyVotingLocationsUrl).then(async response => {
    if (!response.ok) {
      return;
    }
    earlyVotingLocations = await response.json();
  });

  function mouseEnter(event) {
    event.map.getCanvas().style.cursor = "pointer";
  }
  
  function mouseLeave(event) {
    event.map.getCanvas().style.cursor = "";
  }

  let popupData = $state(null);
  let popupLngLat = $state(undefined);
  let popupOpen = $state(false);
  let dialogOpen = $state(false);
  let copied = $state(false);
  let popupContentElement = $state(null);
  let popupMeasurementElement = $state(null);
  let copyFeedbackTimeout = $state(null);
  let dialogElement = $state(null);
  let dialogSurfaceElement = $state(null);
  let openingAddressDetails = $state(false);
  let suppressNextPopupClose = false;

  const REVERT_COPY_BUTTON_TIMEOUT = 10000;
  const POPUP_VIEWPORT_MARGIN = 32;

  function clearCopyFeedbackTimeout() {
    if (copyFeedbackTimeout !== null) {
      clearTimeout(copyFeedbackTimeout);
      copyFeedbackTimeout = null;
    }
  }

  function resetCopyFeedback() {
    clearCopyFeedbackTimeout();
    copied = false;
  }

  onDestroy(() => {
    clearCopyFeedbackTimeout();
  });

  function closeAddressDetails() {
    if (dialogElement !== null  &&  dialogElement.open) {
      dialogElement.close();
    }
    openingAddressDetails = false;
    popupData = null;
    popupLngLat = undefined;
    popupOpen = false;
    dialogOpen = false;
    suppressNextPopupClose = false;
    resetCopyFeedback();
  }

  function expandedPopupWouldOverflowViewport() {
    if (popupMeasurementElement === null) {
      return false;
    }
    return popupMeasurementElement.getBoundingClientRect().height > window.innerHeight - POPUP_VIEWPORT_MARGIN;
  }

  async function decideHowToOpenAddressDetails() {
    await tick();
    await new Promise(resolve => requestAnimationFrame(resolve));

    const useDialog = expandedPopupWouldOverflowViewport();
    dialogOpen = useDialog;
    popupOpen = !useDialog;
    openingAddressDetails = false;
  }

  function handlePopupClose() {
    if (suppressNextPopupClose) {
      suppressNextPopupClose = false;
      return;
    }
    closeAddressDetails();
  }

  function handleDialogCancel(event) {
    event.preventDefault();
    closeAddressDetails();
  }

  function handleDetailsToggle() {}

  async function handleClick(event) {
    let p = event.features[0].properties;
    let isMuni = p.muni != "Unincorporated"  &&  p.muni != "Undefined";
    let unit = p.unit == "" ? "" : ` (${p.unit})`;
    popupData = {
      streetAddressHeader: p.unit == "" ? "Street address" : "Street address (and unit)",
      streetAddress: (p.num >= 0 ? p.num.toString() + " " : "") + p.street + unit,
      cityHeader: isMuni ? "Municipality" : "911 Community (MSAG)",
      city: isMuni ? p.muni : p.msag,
      zip: p.zip,
      district: p.district?.trim?.() ?? "",
      lon: p.lon,
      lat: p.lat,
      county_fp: p.county_fp,
      in_wheretovote: p.in_wheretovote,
      polling_places: p.polling_places,
      src_title: sourceList[p.src].title,
      src_name: sourceList[p.src].name,
      src_phone: sourceList[p.src].phone,
      src_email: sourceList[p.src].email
    };
    popupData.addrToCopy = `${popupData.streetAddress}, ${popupData.city}, ND, ${popupData.zip}`;
    popupLngLat = [p.lon, p.lat];
    dialogOpen = false;
    popupOpen = false;
    openingAddressDetails = true;
    suppressNextPopupClose = false;
    resetCopyFeedback();
    await decideHowToOpenAddressDetails();
  }

  function copyAddress(text) {
    navigator.clipboard.writeText(text);
  }

  function handleCopy(event) {
    copyAddress(popupData.addrToCopy);
    clearCopyFeedbackTimeout();
    copied = true;
    copyFeedbackTimeout = setTimeout(() => {
      copied = false;
      copyFeedbackTimeout = null;
    }, REVERT_COPY_BUTTON_TIMEOUT);
  }

  function handleBallotpediaLookup(event) {
    copyAddress(`${popupData.addrToCopy}, USA`);
  }

  function handleWhereToVoteLookup(event) {
    let houseNumber = popupData?.streetAddress.match(/^\d+/)?.[0] ?? "";
    copyAddress(houseNumber);
  }

  function getPollingPlacesSection(popupData) {
    if (popupData?.polling_places == "") {
      return null;
    }

    const origin = `${popupData?.lat},${popupData?.lon}`;
    const entries = popupData.polling_places
      .split(" ")
      .map(x => Number(x))
      .filter(x => Number.isInteger(x)  &&  x >= 0  &&  x < pollingPlaces.length)
      .map(x => pollingPlaces[x])
      .map(place => {
        const coordinates = pollingPlaceLocations[place.polling_location];
        return {
          polling_location: place.polling_location,
          addressLine: `${place.address}, ${place.city} ${place.zip_code}`,
          polling_hours: place.polling_hours,
          county_auditor_phone: place.county_auditor_phone,
          url: getDirectionsUrl(origin, coordinates),
        };
      });

    if (entries.length == 0) {
      return null;
    }

    return {
      title: popupData?.in_wheretovote
        ? "Polling Places (from WhereToVote)"
        : "Polling Places (inferred from location)",
      entries,
    };
  }

  function insert_break_near(text, targetLength) {
    if (text.length <= targetLength) {
      return text;
    }

    let bestIndex = -1;
    let bestDistance = Infinity;
    for (let i = 0;  i < text.length;  i++) {
      if (text[i] != " ") {
        continue;
      }
      const distance = Math.abs(i - targetLength);
      if (distance < bestDistance) {
        bestDistance = distance;
        bestIndex = i;
      }
    }

    if (bestIndex == -1) {
      return text;
    }

    return text.slice(0, bestIndex) + "<br>" + text.slice(bestIndex + 1);
  }

  function getDropboxEntries(popupData) {
    const countyFp = Number(popupData?.county_fp);
    if (!Number.isFinite(countyFp)) {
      return [];
    }

    const origin = `${popupData?.lat},${popupData?.lon}`;
    let rows = dropboxes.filter(dropbox => Number(dropbox.county_fp) == countyFp);
    if (countyFp == SIOUX_COUNTY_FP) {
      // Sioux lists its dated Absentee Voting Days on the drop-box tab too; those
      // go in their own time-filtered section (getSiouxVoteCenterEntries). Also
      // drop the bare courthouse row: it has no hours and duplicates the
      // "(Drop Box)" row at the same address.
      rows = rows.filter(dropbox => !isAbsenteeVotingDay(dropbox.polling_hours));
      const addressesWithHours = new Set(
        rows.filter(dropbox => dropbox.polling_hours != "").map(dropbox => dropbox.address)
      );
      rows = rows.filter(
        dropbox => dropbox.polling_hours != "" || !addressesWithHours.has(dropbox.address)
      );
    }
    return rows
      .map(dropbox => {
        const coordinates = dropboxLocations[dropbox.polling_location];
        return {
          polling_location: dropbox.polling_location,
          addressLine: `${dropbox.address}, ${dropbox.city} ${dropbox.zip_code}`,
          polling_hours_html: insert_break_near(dropbox.polling_hours, 40),
          county_auditor_phone: dropbox.county_auditor_phone,
          url: getDirectionsUrl(origin, coordinates),
        };
      });
  }

  // Early voting is keyed by county, exactly like dropboxes (unlike polling places,
  // which are looked up by row index from the Parquet's polling_places column).
  //
  // The Secretary of State uses this tab for two different things: statutory early
  // voting (with a Date/Times list) and one-off "Absentee Voting Day" events, which
  // carry their dates in the comments field instead. Both are rendered verbatim in
  // the state's own words rather than relabelled, because getting that wrong could
  // send someone to a closed building. See docs/known-gaps.md.
  /** @param {any} popupData */
  function getEarlyVotingEntries(popupData) {
    const countyFp = Number(popupData?.county_fp);
    if (!Number.isFinite(countyFp)) {
      return [];
    }

    const origin = `${popupData?.lat},${popupData?.lon}`;
    return earlyVoting
      .filter(entry => Number(entry.county_fp) == countyFp)
      // Sioux's Absentee Voting Days are shown by getSiouxVoteCenterEntries instead.
      .filter(entry => countyFp != SIOUX_COUNTY_FP
        || !isAbsenteeVotingDay(`${entry.early_voting_times} ${entry.comments}`))
      .map(entry => {
        const coordinates = earlyVotingLocations[entry.early_voting_location];
        return {
          early_voting_location: entry.early_voting_location,
          addressLine: `${entry.address}, ${entry.city} ${entry.zip_code}`,
          early_voting_times: entry.early_voting_times,
          comments: entry.comments,
          url: getDirectionsUrl(origin, coordinates),
        };
      });
  }

  // Sioux County's one-evening "Absentee Voting Day" events, which the state lists
  // on both the drop-box and early-voting tabs. Unlike every other section, this
  // one hides entries that are already over (judged in Sioux County's local time;
  // see SIOUX_EVENT_TIME_ZONE), because a past date read as an upcoming one would
  // send someone to an empty building. The state's wording is still shown verbatim.
  /** @param {any} popupData */
  function getSiouxVoteCenterEntries(popupData) {
    if (Number(popupData?.county_fp) != SIOUX_COUNTY_FP) {
      return [];
    }

    const origin = `${popupData?.lat},${popupData?.lon}`;
    /**
     * @param {string} name
     * @param {any} row
     * @param {string} hours
     * @param {any} locations
     */
    const toEntry = (name, row, hours, locations) => ({
      name,
      addressLine: `${row.address}, ${row.city} ${row.zip_code}`,
      hours,
      url: getDirectionsUrl(origin, locations[name]),
    });
    const fromDropboxes = dropboxes
      .filter(row => Number(row.county_fp) == SIOUX_COUNTY_FP)
      .filter(row => isAbsenteeVotingDay(row.polling_hours))
      .map(row => toEntry(row.polling_location, row, row.polling_hours, dropboxLocations));
    const fromEarlyVoting = earlyVoting
      .filter(row => Number(row.county_fp) == SIOUX_COUNTY_FP)
      .map(row => ({ row, hours: [row.early_voting_times, row.comments].filter(Boolean).join(" ") }))
      .filter(({ hours }) => isAbsenteeVotingDay(hours))
      .map(({ row, hours }) => toEntry(row.early_voting_location, row, hours, earlyVotingLocations));

    // Soonest first; anything whose date cannot be parsed goes last.
    const end = (/** @type {any} */ entry) => absenteeVotingDayEnd(entry.hours) ?? Infinity;
    return dedupeLocations([...fromDropboxes, ...fromEarlyVoting])
      .filter(entry => !absenteeVotingDayHasEnded(entry.hours))
      .sort((a, b) => end(a) - end(b));
  }

  $effect(() => {
    if (!popupOpen  &&  !dialogOpen  &&  !openingAddressDetails  &&  popupData !== null) {
      popupData = null;
      popupLngLat = undefined;
      resetCopyFeedback();
    }
  });

  $effect(() => {
    if (dialogElement === null) {
      return;
    }

    if (dialogOpen) {
      if (!dialogElement.open) {
        dialogElement.showModal();
        requestAnimationFrame(() => {
          dialogSurfaceElement?.focus();
        });
      }
    }
    else if (dialogElement.open) {
      dialogElement.close();
    }
  });

</script>

<GeoJSON
  id="addresses"
  data={{type: "FeatureCollection", "features": []}}
  attribution={'<a target="_blank" href="https://gishubdata-ndgov.hub.arcgis.com/datasets/NDGOV::ndgishub-site-structure-address-points/about">North Dakota 911 address dataset</a>'}
  >
  <CircleLayer
    id="address-circles"
    source="addresses"
    onmouseenter={mouseEnter}
    onmouseleave={mouseLeave}
    onclick={handleClick}
    minzoom={MIN_ZOOM_FOR_POINTS}
    paint={{
        "circle-color": "#5ef2de",
        "circle-stroke-width": [
          "interpolate", ["linear"], ["zoom"], 11, 0, 13, 0.5, 17, 2
        ],
        "circle-stroke-color": "black",
        "circle-radius": [
          "interpolate", ["linear"], ["zoom"], MIN_ZOOM_FOR_POINTS, 0, 13, 3, 17, 8
        ],
        "circle-stroke-opacity": {
          "base": 1,
          "stops": [[11, 0], [13, 1], [20, 1]]
        },
        "circle-opacity": {
          "base": 1,
          "stops": [[MIN_ZOOM_FOR_POINTS, 0], [MIN_ZOOM_FOR_POINTS + 1, 1], [20, 1]]
        }
      }}
    beforeLayerType="symbol"
  />
</GeoJSON>

<Popup
  closeButton={true}
  openOn="manual"
  bind:open={popupOpen}
  bind:lngLat={popupLngLat}
  onclose={handlePopupClose}
>
  {#if popupData !== null}
    <div bind:this={popupContentElement}>
      <AddressDetailsContent
        {popupData}
        pollingPlacesSection={getPollingPlacesSection(popupData)}
        dropboxEntries={getDropboxEntries(popupData)}
        earlyVotingEntries={getEarlyVotingEntries(popupData)}
        voteCenterEntries={getSiouxVoteCenterEntries(popupData)}
        {copied}
        onCopy={handleCopy}
        onBallotpediaLookup={handleBallotpediaLookup}
        onWhereToVoteLookup={handleWhereToVoteLookup}
        onDetailsToggle={handleDetailsToggle}
      />
    </div>
  {/if}
</Popup>

<dialog
  bind:this={dialogElement}
  class="addressDialog"
  oncancel={handleDialogCancel}
  onclick={(event) => {
    if (event.target === dialogElement) {
      closeAddressDetails();
    }
  }}
>
  {#if dialogOpen && popupData !== null}
    <div class="addressDialogSurface" bind:this={dialogSurfaceElement} tabindex="-1">
      <AddressDetailsContent
        {popupData}
        pollingPlacesSection={getPollingPlacesSection(popupData)}
        dropboxEntries={getDropboxEntries(popupData)}
        earlyVotingEntries={getEarlyVotingEntries(popupData)}
        voteCenterEntries={getSiouxVoteCenterEntries(popupData)}
        {copied}
        onCopy={handleCopy}
        onBallotpediaLookup={handleBallotpediaLookup}
        onWhereToVoteLookup={handleWhereToVoteLookup}
        onDetailsToggle={handleDetailsToggle}
        showClose={true}
        onClose={closeAddressDetails}
      />
    </div>
  {/if}
</dialog>

{#if popupData !== null}
  <div class="popupMeasurementShell">
    <div class="popupMeasurementContent" bind:this={popupMeasurementElement}>
      <AddressDetailsContent
        {popupData}
        pollingPlacesSection={getPollingPlacesSection(popupData)}
        dropboxEntries={getDropboxEntries(popupData)}
        earlyVotingEntries={getEarlyVotingEntries(popupData)}
        voteCenterEntries={getSiouxVoteCenterEntries(popupData)}
        {copied}
        onCopy={handleCopy}
        onBallotpediaLookup={handleBallotpediaLookup}
        onWhereToVoteLookup={handleWhereToVoteLookup}
        onDetailsToggle={handleDetailsToggle}
        expandAllDetails={true}
      />
    </div>
  </div>
{/if}

<style>
  .popupMeasurementShell {
    position: fixed;
    top: 0;
    left: -10000px;
    visibility: hidden;
    pointer-events: none;
  }

  .popupMeasurementContent {
    width: 240px;
    padding: 15px 10px;
    box-sizing: border-box;
    background: white;
  }

  .addressDialog {
    padding: 0;
    border: 0;
    background: transparent;
    max-width: none;
    max-height: none;
  }

  .addressDialogSurface {
    max-width: min(560px, calc(100vw - 24px));
    max-height: calc(100vh - 24px);
    overflow-y: auto;
    padding: 12px 14px;
    border: 1px solid #808080;
    border-radius: 12px;
    background: white;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.35);
  }

  .addressDialog::backdrop {
    background: rgba(0, 0, 0, 0.25);
  }

</style>
