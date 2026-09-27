import assert from "node:assert/strict";
import test from "node:test";

import {
  coarsenCoordinates,
  deniedPermissionState,
  isWithinRecommendationArea,
  shouldRequestPermission,
} from "./locationPolicy.ts";

test("precise coordinates are reduced before recommendation requests", () => {
  assert.deepEqual(coarsenCoordinates(48.1485965, 17.1077478), {
    latitude: 48.149,
    longitude: 17.108,
  });
});

test("locations outside the Bratislava feed area fall back to citywide ranking", () => {
  assert.equal(isWithinRecommendationArea(48.149, 17.108), true);
  assert.equal(isWithinRecommendationArea(52.52, 13.405), false);
});

test("denied and permanently blocked permissions remain distinct", () => {
  assert.equal(deniedPermissionState({ granted: false, canAskAgain: true }), "denied");
  assert.equal(deniedPermissionState({ granted: false, canAskAgain: false }), "blocked");
});

test("permission prompts only occur after an explicit enable action", () => {
  const permission = { granted: false, canAskAgain: true };
  assert.equal(shouldRequestPermission(true, false, permission), false);
  assert.equal(shouldRequestPermission(false, true, permission), false);
  assert.equal(shouldRequestPermission(true, true, permission), true);
});
