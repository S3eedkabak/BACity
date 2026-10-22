import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
const read=path=>readFile(new URL(path,import.meta.url),'utf8');
const digest=value=>createHash('sha256').update(value).digest('hex');

test('pre-task map styles and toilet layers stay intact in the shared screen',async()=>{
  const source=await read('./MapScreen.tsx');
  const baseline=JSON.parse(await read('./fixtures/pre-task-map.json'));
  assert.equal(digest(source.slice(source.indexOf('const styles = StyleSheet.create('))),baseline.styles);
  const start=source.indexOf('        {showUtilities && <ShapeSource');
  const end=source.indexOf('</ShapeSource>}',start)+'</ShapeSource>}'.length;
  assert.equal(digest(source.slice(start,end)),baseline.toilets);
  assert.match(source,/https:\/\/tiles.openfreemap.org\/styles\/liberty/);
  for(const label of ['Search events','Show events near me','Show public toilet map layer','Browse all city utilities','Zoom in','Zoom out','Recenter map'])assert.ok(source.includes(label),label);
  assert.match(source,/NEARBY_RADIUS_KM = 3/);
  assert.match(source,/followUserLocation=\{nearMeActive\}/);
  assert.match(source,/mergeViewportUtilities/);assert.match(source,/OfflineManager.setMaximumAmbientCacheSize/);
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
