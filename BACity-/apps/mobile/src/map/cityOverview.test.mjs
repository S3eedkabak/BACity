import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
import {CITY_NORTH_EAST, CITY_SOUTH_WEST, cityOverviewPadding, webCameraPadding} from './cityOverview.ts';

test('city overview includes every coordinate of all 17 official districts', async () => {
  const data = JSON.parse(await readFile(new URL('../../../../services/api/app/data/bratislava-districts.geojson', import.meta.url)));
  assert.equal(data.features.length, 17);
  function check(coordinates) {
    if (typeof coordinates[0] === 'number') {
      const [lng, lat] = coordinates;
      assert.ok(lng >= CITY_SOUTH_WEST[0] && lng <= CITY_NORTH_EAST[0]);
      assert.ok(lat >= CITY_SOUTH_WEST[1] && lat <= CITY_NORTH_EAST[1]);
    } else coordinates.forEach(check);
  }
  data.features.forEach(feature => check(feature.geometry.coordinates));
});

test('overview reserves safe areas, icon controls and an open event preview', () => {
  assert.deepEqual(cityOverviewPadding(62, 34), [138, 32, 122, 32]);
  assert.deepEqual(cityOverviewPadding(62, 34, 240), [138, 32, 362, 32]);
});

test('web and native cameras use the same edge padding', () => {
  assert.deepEqual(webCameraPadding(cityOverviewPadding(62, 34)), {top: 138, right: 32, bottom: 122, left: 32});
  assert.deepEqual(webCameraPadding([80, 24]), {top: 80, right: 24, bottom: 80, left: 24});
  assert.equal(webCameraPadding(40), 40);
});
