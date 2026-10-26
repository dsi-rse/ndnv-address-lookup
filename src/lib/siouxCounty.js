/**
 * Sioux County helpers for the address popup.
 *
 * Sioux County -- the North Dakota part of the Standing Rock Reservation -- had NO
 * entries in North Dakota's NG911 dataset until October 2026, when 1,725 address
 * points appeared. Those addresses get the ordinary popup. What is special here is
 * the county's one-evening "Absentee Voting Day" events: the popup lists them in
 * their own section and hides each one once it is over (AddressesLayer.svelte,
 * getSiouxVoteCenterEntries).
 *
 * Everything factual is read at runtime from the same CSVs the rest of the app uses,
 * so it stays correct when scripts/step1-update-polling-places.py is re-run.
 */

/** Census-style county FIPS used throughout the app: 2 * 43 - 1. */
export const SIOUX_COUNTY_FP = 85;

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
