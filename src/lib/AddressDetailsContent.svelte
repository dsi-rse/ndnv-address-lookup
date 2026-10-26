<script>
  /** @type {any} */
  export let popupData = null;
  /** @type {any} */
  export let pollingPlacesSection = null;
  /** @type {any[]} */
  export let dropboxEntries = [];
  /** @type {any[]} */
  export let earlyVotingEntries = [];
  /** @type {any[]} */
  export let voteCenterEntries = [];
  export let copied = false;
  export let onCopy = () => {};
  export let onBallotpediaLookup = () => {};
  export let onWhereToVoteLookup = () => {};
  export let onDetailsToggle = () => {};
  export let showClose = false;
  export let onClose = () => {};
  export let expandAllDetails = false;
</script>

<div class="detailsCard">
  {#if showClose}
    <button
      type="button"
      class="dialogCloseButton"
      aria-label="Close"
      onclick={onClose}
    >&#215;</button>
  {/if}

  <div class="detailsBody">
    <strong class="sectionTitle">Address:</strong><br>
    <strong>{popupData?.streetAddressHeader}:</strong> {popupData?.streetAddress}<br>
    <strong>{popupData?.cityHeader}:</strong> {popupData?.city}<br>
    <strong>Zip code:</strong> {popupData?.zip}<br>
    <details open={expandAllDetails} ontoggle={onDetailsToggle}>
      <summary><strong>Source</strong></summary>
      <strong>{popupData?.src_title}</strong><br>
      <strong>Name:</strong> {popupData?.src_name}<br>
      {#if popupData?.src_phone}
        <strong>Phone:</strong> {popupData?.src_phone}<br>
      {/if}
      {#if popupData?.src_email}
        <strong>Email:</strong> <a href="mailto:{popupData?.src_email}">{popupData?.src_email}</a>
      {/if}
    </details>
    <br>

    <strong class="sectionTitle">Voter Information:</strong><br>
    <a
      href="https://ndlegis.gov/districts/2025-2032/district-{popupData?.district.replace(/[AB]$/, '')}"
      target="_blank"
      rel="noreferrer"
    >Legislative District {popupData?.district}</a>
    <br>
    <a
      href="https://ballotpedia.org/Sample_Ballot_Lookup"
      target="_blank"
      rel="noreferrer"
      onclick={onBallotpediaLookup}
    >Copy address and go to Ballotpedia</a>
    <br>
    <a
      href="https://vip.sos.nd.gov/WhereToVote.aspx"
      target="_blank"
      rel="noreferrer"
      onclick={onWhereToVoteLookup}
    >Copy number and go to WhereToVote</a><br>

    {#if pollingPlacesSection !== null && pollingPlacesSection.entries.length != 0}
      <br>
      <details open={expandAllDetails} ontoggle={onDetailsToggle}>
        <summary><strong>{pollingPlacesSection.title}</strong></summary>
        {#each pollingPlacesSection.entries as place, i}
          {#if i != 0}<br><br>{/if}
          {place.polling_location}<br>
          {#if place.url !== null}
            <a href={place.url} target="_blank" rel="noreferrer">{place.addressLine}</a>
          {:else}
            {place.addressLine}
          {/if}
          <br>
          ({place.polling_hours}, {place.county_auditor_phone})
        {/each}
      </details>
    {/if}

    {#if earlyVotingEntries.length != 0}
      <br>
      <details open={expandAllDetails} ontoggle={onDetailsToggle}>
        <summary><strong>Early Voting</strong></summary>
        {#each earlyVotingEntries as early, i}
          {#if i != 0}<br><br>{/if}
          {early.early_voting_location}<br>
          {#if early.url !== null}
            <a href={early.url} target="_blank" rel="noreferrer">{early.addressLine}</a>
          {:else}
            {early.addressLine}
          {/if}
          {#if early.early_voting_times}
            <br>{early.early_voting_times}
          {/if}
          {#if early.comments}
            <br>{early.comments}
          {/if}
        {/each}
      </details>
    {/if}

    {#if dropboxEntries.length != 0}
      <br>
      <details open={expandAllDetails} ontoggle={onDetailsToggle}>
        <summary><strong>County Dropboxes</strong></summary>
        {#each dropboxEntries as dropbox, i}
          {#if i != 0}<br><br>{/if}
          {dropbox.polling_location}<br>
          {#if dropbox.url !== null}
            <a href={dropbox.url} target="_blank" rel="noreferrer">{dropbox.addressLine}</a>
          {:else}
            {dropbox.addressLine}
          {/if}
          <br>
          {@html dropbox.polling_hours_html}<br>
          Phone: {dropbox.county_auditor_phone}
        {/each}
      </details>
    {/if}

    {#if voteCenterEntries.length != 0}
      <br>
      <details open={expandAllDetails} ontoggle={onDetailsToggle}>
        <summary><strong>Vote Centers (Absentee Voting Days)</strong></summary>
        {#each voteCenterEntries as center, i}
          {#if i != 0}<br><br>{/if}
          {center.name}<br>
          {#if center.url !== null}
            <a href={center.url} target="_blank" rel="noreferrer">{center.addressLine}</a>
          {:else}
            {center.addressLine}
          {/if}
          <br>{center.hours}
        {/each}
      </details>
    {/if}
  </div>

  <div class="popupCopyButton">
    <button type="button" onclick={onCopy}>Copy Address</button>
    <span class:visible={copied}>Copied!</span>
  </div>
</div>

<style>
  .detailsCard {
    position: relative;
    color: black;
  }

  .detailsBody {
    padding-right: 20px;
  }

  .sectionTitle {
    text-decoration: underline;
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

  .popupCopyButton {
    display: inline-flex;
    justify-content: center;
    width: 100%;
    margin-top: 24px;
  }

  .popupCopyButton button {
    border: 1px solid #808080;
    background: #f0f0f0;
    color: black;
    font-weight: bold;
  }

  .popupCopyButton span {
    display: none;
    margin-top: 6px;
    margin-bottom: 5px;
    background: white;
    color: black;
    font-weight: bold;
  }

  .popupCopyButton span.visible {
    display: inline;
  }
</style>
