import assert from "node:assert/strict";
import test from "node:test";

import {
  coarsenCoordinates,
  deniedPermissionState,
  isWithinRecommendationArea,
  locationFailureState,
  shouldRequestPermission,
} from "./locationPolicy.ts";
import { excludeFeaturedEvent, selectFeaturedEvent } from "./homeFeed.ts";

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

test("location acquisition failures remain distinguishable", () => {
  assert.equal(locationFailureState({ code: "BACITY_LOCATION_TIMEOUT" }), "timeout");
  assert.equal(locationFailureState({ code: "E_LOCATION_SERVICES_DISABLED" }), "unavailable");
  assert.equal(locationFailureState(new Error("native failure")), "error");
});

test("Home keeps the original first event as hero and removes it from the feed", () => {
  const events = [{ id: "first" }, { id: "second" }];
  const hero = selectFeaturedEvent(events);
  const feed = excludeFeaturedEvent([
    { event: events[0] },
    { event: events[1] },
  ], hero?.id);
  assert.equal(hero?.id, "first");
  assert.deepEqual(feed.map((item) => item.event.id), ["second"]);
});
