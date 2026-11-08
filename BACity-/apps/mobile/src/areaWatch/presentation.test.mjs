import test from "node:test";
import assert from "node:assert/strict";
import { areaWatchEventRoute, areaWatchRoute, resolveAreaWatchView, totalUnseen, validWatchCoordinates } from "./presentation.ts";

test("Area Watch entitlement fails closed without premium content flash", () => {
  assert.equal(resolveAreaWatchView("loading", false, 3), "loading");
  assert.equal(resolveAreaWatchView("paywall", false, 3), "paywall");
  assert.equal(resolveAreaWatchView("error", false, 3), "paywall");
  assert.equal(resolveAreaWatchView("allow", true, 3), "error");
});

test("active Plus sees empty or content states", () => {
  assert.equal(resolveAreaWatchView("allow", false, 0), "empty");
  assert.equal(resolveAreaWatchView("allow", false, 2), "content");
});

test("manual watch coordinates remain finite and inside Bratislava bounds", () => {
  assert.equal(validWatchCoordinates(48.1486, 17.1077), true);
  assert.equal(validWatchCoordinates(Number.NaN, 17.1), false);
  assert.equal(validWatchCoordinates(47, 17.1), false);
});

test("unseen summary and navigation are deterministic", () => {
  assert.equal(totalUnseen([{ unseen_count: 2 }, { unseen_count: 3 }]), 5);
  assert.equal(areaWatchRoute("watch"), "/area-watch/watch");
  assert.equal(areaWatchEventRoute("event"), "/event/event");
});
