<script>
  import Map from './lib/Map.svelte';
  import SearchBox from './lib/SearchBox.svelte';
  import Welcome from './lib/Welcome.svelte';

  let map;

  function handleFlyTo(item) {
    if (map !== null) {
      map.flyTo(item);
    }
  }
</script>

<Map bind:this={map} />

<SearchBox onSelect={handleFlyTo} />

<Welcome />
