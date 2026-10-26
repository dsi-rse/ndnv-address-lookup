/**
 * Sioux County fallback.
 *
 * Sioux County -- the North Dakota part of the Standing Rock Reservation -- had NO
 * entries in North Dakota's NG911 dataset until October 2026, when 1,725 address
 * points appeared. Those addresses now get the ordinary popup; this county-wide box
 * remains for taps between address dots and for searching "Sioux County" or
 * "Standing Rock Reservation".
 *
 * Everything factual here is read at runtime from the same CSVs the rest of the app
 * uses, so it stays correct when scripts/step1-update-polling-places.py is re-run
 * before the election. Only the prose and the county's identity are hardcoded.
 */

import { getDirectionsUrl } from "./directions.js";

/** Census-style county FIPS used throughout the app: 2 * 43 - 1. */
export const SIOUX_COUNTY_FP = 85;
export const SIOUX_COUNTY_NAME = "Sioux";

/** Resolve by `src` string, not by index: source-list.json is a generated file. */
export const SIOUX_911_SRC = "SIOUX COUNTY 911";

/**
 * Sioux is entirely within Legislative District 31 -- verified for all three of its
 * precincts (31-01, 31-02, 31-03) in public/polling-places.parquet.
 */
export const SIOUX_LEGISLATIVE_DISTRICT = "31";

export const SOS_PRECINCTS_URL = "https://vip.sos.nd.gov/Precincts.aspx?eid=348";
export const BALLOTPEDIA_URL = "https://ballotpedia.org/Sioux_County,_North_Dakota";
export const SAMPLE_BALLOT_URL = "https://ballotpedia.org/Sample_Ballot_Lookup";
export const LEGISLATIVE_DISTRICT_URL =
  `https://ndlegis.gov/districts/2025-2032/district-${SIOUX_LEGISLATIVE_DISTRICT}`;

/**
 * Sioux County straddles the Central/Mountain boundary (Fort Yates is Central, the
 * county west of ND 31 is Mountain) and the state's text does not say which one an
 * event uses. Judging every event by Mountain time keeps it listed until the LATER
 * of the two possible closing times: at worst a Central-time event lingers for an
 * hour after it closes, but an open event is never hidden.
 */
export const SIOUX_EVENT_TIME_ZONE = "America/Denver";

const MONTHS = [
  "january", "february", "march", "april", "may", "june",
  "july", "august", "september", "october", "november", "december",
];

// "Absentee Voting Day - October 30th 2026 5pm-7pm"
// "Absentee Voting Day- October 28th, 2026 5pm-7pm"
const ABSENTEE_VOTING_DAY_PATTERN = new RegExp(
  "(" + MONTHS.join("|") + ")\\s+(\\d{1,2})(?:st|nd|rd|th)?,?\\s+(\\d{4})"
  + "\\s+\\d{1,2}(?::\\d{2})?\\s*(?:am|pm)?\\s*-\\s*(\\d{1,2})(?::(\\d{2}))?\\s*(am|pm)",
  "i",
);

/** @param {string} text */
export function isAbsenteeVotingDay(text) {
  return /absentee voting day/i.test(text ?? "");
}

/**
 * The end of an "Absentee Voting Day" as a sortable YYYYMMDDHHMM wall-clock number,
 * or null if the state's wording cannot be parsed.
 *
 * @param {string} text
 * @returns {number | null}
 */
export function absenteeVotingDayEnd(text) {
  const match = ABSENTEE_VOTING_DAY_PATTERN.exec(text ?? "");
  if (match === null) {
    return null;
  }
  const month = MONTHS.indexOf(match[1].toLowerCase()) + 1;
  const day = Number(match[2]);
  const year = Number(match[3]);
  let hour = Number(match[4]) % 12;
  if (match[6].toLowerCase() == "pm") {
    hour += 12;
  }
  const minute = Number(match[5] ?? 0);
  return (((year * 100 + month) * 100 + day) * 100 + hour) * 100 + minute;
}

/**
 * The current wall-clock time in SIOUX_EVENT_TIME_ZONE, in the same form.
 *
 * @param {Date} now
 */
function wallClockNow(now) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-US", {
      timeZone: SIOUX_EVENT_TIME_ZONE,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    })
      .formatToParts(now)
      .map(part => [part.type, part.value])
  );
  return Number(`${parts.year}${parts.month}${parts.day}${parts.hour}${parts.minute}`);
}

/**
 * True only if `text` is an event that has definitely finished. Anything that
 * cannot be parsed counts as NOT ended, so the state's wording is shown rather
 * than silently dropped.
 *
 * @param {string} text
 * @param {Date} [now]
 */
export function absenteeVotingDayHasEnded(text, now = new Date()) {
  const end = absenteeVotingDayEnd(text);
  return end !== null && wallClockNow(now) >= end;
}

/**
 * Collapse the state's overlapping rows for the same place.
 *
 * In Sioux County the drop-box and early-voting tabs describe the same "Absentee
 * Voting Day" events, and the courthouse appears both as a bare row with no hours
 * and as "(Drop Box)" with the real text. So: drop exact duplicates, then drop
 * blank-hours rows whenever another row at the SAME ADDRESS says something.
 *
 * Deliberately dumb -- it never rewrites or reclassifies the state's wording,
 * because guessing which rows are "early voting" versus "drop box" could send
 * someone to a closed building.
 *
 * @param {any[]} rows
 * @returns {any[]}
 */
export function dedupeLocations(rows) {
  /** @type {any[]} */
  const unique = [];
  for (const row of rows) {
    const isDuplicate = unique.some(
      (/** @type {any} */ other) =>
        other.name == row.name
        && other.addressLine == row.addressLine
        && other.hours == row.hours
    );
    if (!isDuplicate) {
      unique.push(row);
    }
  }

  const addressesWithHours = new Set(
    unique
      .filter((/** @type {any} */ row) => row.hours != "")
      .map((/** @type {any} */ row) => row.addressLine)
  );
  return unique.filter(
    (/** @type {any} */ row) =>
      row.hours != "" || !addressesWithHours.has(row.addressLine)
  );
}

/**
 * `data` carries the already-fetched CSV rows and coordinate lookups from
 * AddressesLayer: pollingPlaces, pollingPlaceLocations, dropboxes, dropboxLocations,
 * earlyVoting, earlyVotingLocations, sourceList. Typed loosely to match the rest of
 * this codebase, which parses those CSVs into untyped objects.
 *
 * @param {{lng: number, lat: number}} lngLat - the point the user tapped
 * @param {any} data
 */
export function buildSiouxCountyData(lngLat, data) {
  // Directions start from the tapped point because there is no address to start from.
  const origin = `${lngLat.lat.toFixed(5)},${lngLat.lng.toFixed(5)}`;

  /**
   * @param {string} name
   * @param {string} address
   * @param {string} city
   * @param {string} zip
   * @param {any} locations
   */
  const withUrl = (name, address, city, zip, locations) => {
    const addressLine = `${address}, ${city} ${zip}`;
    return {
      name,
      addressLine,
      // Fall back to the street address so a location we could not geocode still
      // gets a usable link rather than silently losing one.
      url: getDirectionsUrl(origin, locations[name], `${address}, ${city}, ND ${zip}`),
    };
  };

  const pollingPlaces = (data.pollingPlaces ?? [])
    .filter((/** @type {any} */ row) => row.county == SIOUX_COUNTY_NAME)
    .map((/** @type {any} */ row) => ({
      ...withUrl(
        row.polling_location, row.address, row.city, row.zip_code,
        data.pollingPlaceLocations ?? {},
      ),
      hours: row.polling_hours,
      phone: row.county_auditor_phone,
    }));

  const dropboxRows = (data.dropboxes ?? [])
    .filter((/** @type {any} */ row) => Number(row.county_fp) == SIOUX_COUNTY_FP)
    .map((/** @type {any} */ row) => ({
      ...withUrl(
        row.polling_location, row.address, row.city, row.zip_code,
        data.dropboxLocations ?? {},
      ),
      hours: row.polling_hours,
      phone: row.county_auditor_phone,
    }));

  const earlyVotingRows = (data.earlyVoting ?? [])
    .filter((/** @type {any} */ row) => Number(row.county_fp) == SIOUX_COUNTY_FP)
    .map((/** @type {any} */ row) => ({
      ...withUrl(
        row.early_voting_location, row.address, row.city, row.zip_code,
        data.earlyVotingLocations ?? {},
      ),
      hours: [row.early_voting_times, row.comments].filter(Boolean).join(" "),
      phone: "",
    }));

  const coordinator =
    (data.sourceList ?? []).find((/** @type {any} */ entry) => entry.src == SIOUX_911_SRC)
    ?? null;

  return {
    countyName: SIOUX_COUNTY_NAME,
    coordinator,
    // Sioux runs vote centers rather than precinct polling sites, and has exactly
    // one, so precinct does not matter to a voter here.
    pollingPlaces,
    // Absentee Voting Days that are over are dropped, so nobody reads a past date
    // as an upcoming one; the courthouse drop box has no date and always stays.
    absenteeLocations: dedupeLocations([...dropboxRows, ...earlyVotingRows])
      .filter((/** @type {any} */ row) => !absenteeVotingDayHasEnded(row.hours)),
    // The one phone number worth showing at the top; every Sioux row carries it.
    phone:
      pollingPlaces[0]?.phone
      || dropboxRows[0]?.phone
      || coordinator?.phone
      || "",
  };
}
