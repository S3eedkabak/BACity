import assert from "node:assert/strict";
import test from "node:test";
import { groupTonightItems, resolveTonightView, tonightLocationCopy } from "./presentation.ts";

test("entitlement loading and errors never reveal Tonight", () => {
  assert.equal(resolveTonightView("loading", false, false, 2), "guarding");
  assert.equal(resolveTonightView("error", false, false, 2), "guarding");
  assert.equal(resolveTonightView("paywall", false, false, 2), "guarding");
});

test("Tonight exposes explicit loading, API error, empty and result states", () => {
  assert.equal(resolveTonightView("allow", true, false, 0), "loading");
  assert.equal(resolveTonightView("allow", false, true, 0), "error");
  assert.equal(resolveTonightView("allow", false, false, 0), "empty");
  assert.equal(resolveTonightView("allow", false, false, 1), "results");
});

test("results group in decision order without fabricating events", () => {
  const item = classification => ({ classification, event: { id: classification }, reasons: [], saved: false });
  const sections = groupTonightItems([item("later_tonight"), item("happening_now"), item("starting_soon")]);
  assert.deepEqual(sections.map(section => section.title), ["Happening now", "Starting soon", "Later tonight"]);
  assert.equal(sections.flatMap(section => section.data).length, 3);
});

test("location copy distinguishes optional citywide and approximate modes", () => {
  assert.equal(tonightLocationCopy(false), "Showing citywide Bratislava picks");
  assert.equal(tonightLocationCopy(true), "Using an approximate current location");
});
