import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
const read=path=>readFile(new URL(path,import.meta.url),'utf8');

test('map cleanup retains caching, utility clustering and accessible icon controls',async()=>{
  const source=await read('./MapScreen.tsx');
  assert.match(source,/https:\/\/tiles.openfreemap.org\/styles\/liberty/);
  for(const label of ['Show public toilet map layer','Hide public toilet map layer','Browse all city utilities','Map event filters and area events','Recenter map to show all Bratislava'])assert.ok(source.includes(label),label);
  for(const removed of ['Search events','Show events near me','Zoom in','Zoom out','events on the map','Find events','Filters / Area'])assert.ok(!source.includes(removed),removed);
  assert.match(source,/accessibilityState=\{\{ selected: showUtilities \}\}/);
  assert.match(source,/iconImage: "restroom"/);
  assert.doesNotMatch(source,/circleColor: colors.free/);
  assert.match(source,/clusterMaxZoomLevel=\{14\}/);
  assert.match(source,/mergeViewportUtilities/);
  assert.match(source,/OfflineManager.setMaximumAmbientCacheSize/);
  // Network errors remain visible without a permanent event-count banner.
  assert.match(source,/dataUnavailable \|\| basemapUnavailable \|\| \(isRefreshing && !hasCachedLayer\)/);
  assert.match(source,/cameraRef.current\?\.fitBounds\(/);
});

test('both routes share the original screen and keep utility/area interactions separate',async()=>{
  for(const path of ['../../app/(tabs)/map.tsx','../../app/(tabs)/map.web.tsx'])assert.match(await read(path),/src\/map\/MapScreen['"]/);
  const source=await read('./MapScreen.tsx');
  assert.match(source,/id="map-events"/);assert.match(source,/id="public-toilets"/);assert.match(source,/id="city-districts"/);
  assert.match(source,/pathname: "\/utility\/\[id\]"/);assert.match(source,/router.push\("\/event\/"/);
  assert.match(source,/mapSession.camera/);assert.match(source,/mapSession.filters/);
  const utilities=await read('../../app/utilities.tsx');
  for(const kind of ['toilet','water_fountain','bike_repair','charging','wifi','bench','playground','dog_park','recycling','accessible_entrance','parking','locker'])assert.ok(utilities.includes(`"${kind}"`));
});

test('districts are geographic targets and cluster camera does not fit empty grid cells',async()=>{
  const source=await read('./MapScreen.tsx');
  assert.ok(!source.includes('Browse city districts'));
  assert.ok(!source.includes('visible={areasOpen}'));
  assert.match(source,/setSelectedDistrict\(String\(properties.id\)\)/);
  assert.match(source,/!showUtilities && nearMeActive && !target && <ShapeSource/);
  assert.match(source,/districtBoundaryLines/);
  assert.match(source,/markerPressedAt/);
  assert.match(source,/clusterCamera\(selected,zoomLevel\)/);
  assert.match(source,/!zoomChanged&&containsBounds/);
  assert.match(source,/id="city-district-name"/);
  assert.match(source,/textField:\['get','name'\]/);
  assert.match(source,/id="city-district-count"/);
  assert.doesNotMatch(source,/id="city-district-count-disc"/);
  assert.match(source,/No events/);
  assert.ok(!source.includes("['concat',['get','name'],' · '"));
  assert.match(source,/morphRings\(feature,projection,viewport\)/);
});
