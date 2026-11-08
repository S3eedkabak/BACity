import assert from "node:assert/strict";
import test from "node:test";
import { eventChainsRoute, eventDetailRoute, isValidRenderedChain, resolveEventChainsView } from "./presentation.ts";

test("entitlement loading and failure never reveal chains", () => {
  assert.equal(resolveEventChainsView("loading", false, false, 2), "guarding");
  assert.equal(resolveEventChainsView("error", false, false, 2), "guarding");
  assert.equal(resolveEventChainsView("paywall", false, false, 2), "guarding");
});

test("screen has explicit loading, API error, empty, partial and result states", () => {
  assert.equal(resolveEventChainsView("allow", true, false, 0), "loading");
  assert.equal(resolveEventChainsView("allow", false, true, 0), "error");
  assert.equal(resolveEventChainsView("allow", false, false, 0), "empty");
  assert.equal(resolveEventChainsView("allow", false, false, 1), "results");
});

test("rendered chain keeps exactly one anchor in temporal order", () => {
  const item = (id, relation, is_anchor = false) => ({ event: { id }, relation, is_anchor, reasons: [] });
  assert.equal(isValidRenderedChain({ id: "chain-1", items: [
    item("before", "before"), item("anchor", "anchor", true), item("after", "after"),
  ] }, "anchor"), true);
  assert.equal(isValidRenderedChain({ id: "partial", items: [
    item("anchor", "anchor", true), item("after", "after"),
  ] }, "anchor"), true);
  assert.equal(isValidRenderedChain({ id: "bad", items: [
    item("anchor", "anchor", true), item("anchor", "anchor", true),
  ] }, "anchor"), false);
});

test("entry and event rows target dedicated and normal detail routes", () => {
  assert.deepEqual(eventChainsRoute("anchor-1"), { pathname: "/event-chains", params: { anchorEventId: "anchor-1" } });
  assert.equal(eventDetailRoute("event-2"), "/event/event-2");
});
