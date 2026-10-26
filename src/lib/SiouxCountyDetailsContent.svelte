<script>
  /** @type {any} */
  export let data = null;
  /** @type {() => void} */
  export let onClose = () => {};

  import {
    BALLOTPEDIA_URL,
    LEGISLATIVE_DISTRICT_URL,
    SAMPLE_BALLOT_URL,
    SIOUX_LEGISLATIVE_DISTRICT,
    SOS_PRECINCTS_URL,
  } from "./siouxCounty.js";
</script>

<div class="siouxCard">
  <div class="siouxHeader">
    <button
      type="button"
      class="dialogCloseButton"
      aria-label="Close"
      onclick={onClose}
    >&times;</button>
  </div>

  <div class="siouxBody">
    <p class="siouxLead">
      Sioux County addresses were added to North Dakota's 911 address dataset in October 2026.
      Zoom in and tap an address to see its details. This box lists voting information for the whole county.
    </p>

    {#if data?.coordinator !== null && data?.coordinator !== undefined}
      <details>
        <summary><strong>Who to contact if your address is missing or wrong</strong></summary>
        <strong>{data.coordinator.title}</strong><br>
        <strong>Name:</strong> {data.coordinator.name}<br>
        {#if data.coordinator.phone}
          <strong>Phone:</strong> {data.coordinator.phone}<br>
        {/if}
        {#if data.coordinator.email}
          <strong>Email:</strong>
          <a href={`mailto:${data.coordinator.email}`}>{data.coordinator.email}</a>
        {/if}
      </details>
    {/if}

    {#if data?.pollingPlaces?.length}
      <strong class="sectionTitle">Where to vote on Election Day</strong>
      {#each data.pollingPlaces as place}
        <div class="siouxEntry">
          {place.name}<br>
          {#if place.url !== null}
            <a href={place.url} target="_blank" rel="noreferrer">{place.addressLine}</a><sup>*</sup>
          {:else}
            {place.addressLine}
          {/if}
          {#if place.hours}<br>{place.hours}{/if}
          {#if place.phone}<br>Phone: {place.phone}{/if}
        </div>
      {/each}
      <p class="siouxNote">
        Sioux County uses vote centers rather than precinct polling sites, and has
        {data.pollingPlaces.length == 1 ? "only one" : `${data.pollingPlaces.length}`}.
        Any Sioux County voter may vote
        {data.pollingPlaces.length == 1 ? "here" : "at any of them"}, no matter which
        precinct they live in.
      </p>
    {/if}

    {#if data?.absenteeLocations?.length}
      <strong class="sectionTitle">Where to go for early voting (absentee and drop box)</strong>
      {#each data.absenteeLocations as spot}
        <div class="siouxEntry">
          <span style="font-weight: bold;">{spot.name}</span><br>
          {#if spot.url !== null}
            <a href={spot.url} target="_blank" rel="noreferrer">{spot.addressLine}</a><sup>*</sup>
          {:else}
            {spot.addressLine}
          {/if}
          {#if spot.hours}<br>{spot.hours}{/if}
        </div>
      {/each}
    {/if}

    <p class="siouxNote">
      <sup>*</sup>Driving directions start from the spot you clicked or tapped on the map.
    </p>

    <strong class="sectionTitle">More information</strong>
    <div class="siouxEntry">
      <a href={LEGISLATIVE_DISTRICT_URL} target="_blank" rel="noreferrer"
        >Legislative District {SIOUX_LEGISLATIVE_DISTRICT}</a><br>
      <a href={BALLOTPEDIA_URL} target="_blank" rel="noreferrer"
        >Sioux County on Ballotpedia</a><br>
      <a href={SAMPLE_BALLOT_URL} target="_blank" rel="noreferrer"
        >Look up a sample ballot by street address</a><br>
      <a href={SOS_PRECINCTS_URL} target="_blank" rel="noreferrer"
        >Source: ND Secretary of State polling places</a>
    </div>

  </div>
</div>

<style>
  /* Deliberately duplicated from AddressDetailsContent rather than hoisted to a
     global stylesheet: this box must not be able to affect the address popup. */
  .siouxCard {
    position: relative;
    color: black;
    background: white;
  }

  .siouxHeader {
    position: sticky;
    top: 0;
    z-index: 1;
    padding-bottom: 6px;
    background: white;
  }

  .siouxTitle {
    display: block;
    padding-right: 24px;
    text-decoration: underline;
  }

  .siouxBody {
    overflow-wrap: break-word;
  }

  .siouxBody p {
    margin: 8px 0;
  }

  .siouxLead {
    font-weight: bold;
  }

  .siouxNote {
    color: #454545;
  }

  .sectionTitle {
    display: block;
    margin-top: 14px;
    text-decoration: underline;
  }

  .siouxEntry {
    display: block;
    padding: 6px 0;
  }

  /* ~44px effective tap targets on a phone, with 8+ links in this box. */
  .siouxEntry a,
  .siouxBody p a {
    display: inline-block;
    padding: 0 0;
  }

  .dialogCloseButton {
    position: absolute;
    top: 0;
    right: 0;
    border: 0;
    padding: 0 4px;
    background: transparent;
    color: #757575;
    font-size: 24px;
    line-height: 1;
    cursor: pointer;
  }

  .dialogCloseButton:hover {
    color: black;
  }
</style>
