<script>
  import Map from './lib/Map.svelte';
  import SearchBox from './lib/SearchBox.svelte';
  import Welcome from './lib/Welcome.svelte';

  let map;

  // Searching "Sioux County" or "Standing Rock Reservation" flies you to a whole
  // county, too far out to see address dots. Those searchers are exactly the
  // people the county-wide box is for, so open it for them. A DOM event keeps this
  // from needing a store or a prop chain down to AddressesLayer.
  const SIOUX_SEARCH_NAMES = ["Sioux County", "Standing Rock Reservation"];

  function handleFlyTo(item) {
    if (map !== null) {
      map.flyTo(item);
    }
    if (SIOUX_SEARCH_NAMES.includes(item?.name)) {
      window.dispatchEvent(
        new CustomEvent("open-sioux-box", { detail: { coords: item.coords } })
      );
    }
  }
</script>

<Map bind:this={map} />

<SearchBox onSelect={handleFlyTo} />

<Welcome />
