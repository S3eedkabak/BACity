import test from "node:test";
import assert from "node:assert/strict";
import { dismissPlusPaywall, plusPaywallRoute, resolvePlusAction, resolvePlusGate } from "./policy.ts";

test("free, active Plus, and expired canonical states gate correctly", () => {
  assert.equal(resolvePlusGate({ authenticated: true, pending: false, failed: false, active: false }), "paywall");
  assert.equal(resolvePlusGate({ authenticated: true, pending: false, failed: false, active: true }), "allow");
  const expired = { active: false, expires_at: "2020-01-01T00:00:00Z" };
  assert.equal(resolvePlusGate({ authenticated: true, pending: false, failed: false, active: expired.active }), "paywall");
});

test("loading and request failure never grant access", () => {
  assert.equal(resolvePlusGate({ authenticated: true, pending: true, failed: false, active: false }), "loading");
  assert.equal(resolvePlusGate({ authenticated: true, pending: false, failed: true, active: false }), "error");
  assert.equal(resolvePlusGate({ authenticated: false, pending: false, failed: false, active: false }), "paywall");
});

test("premium action has feature-scoped paywall navigation while Plus permits callback", () => {
  assert.deepEqual(plusPaywallRoute("tonight"), {
    pathname: "/plus", params: { feature: "tonight" },
  });
  assert.deepEqual(resolvePlusAction("paywall", "event_chains"), {
    kind: "paywall", route: { pathname: "/plus", params: { feature: "event_chains" } },
  });
  assert.deepEqual(resolvePlusAction("error", "event_chains"), {
    kind: "paywall", route: { pathname: "/plus", params: { feature: "event_chains", unavailable: "1" } },
  });
  assert.deepEqual(resolvePlusAction("allow", "event_chains"), { kind: "allow" });
  assert.deepEqual(resolvePlusAction("loading", "event_chains"), { kind: "wait" });
  assert.deepEqual(plusPaywallRoute("build_my_evening"), {
    pathname: "/plus", params: { feature: "build_my_evening" },
  });
  assert.deepEqual(plusPaywallRoute("area_watch", true), {
    pathname: "/plus", params: { feature: "area_watch", unavailable: "1" },
  });
  assert.deepEqual(resolvePlusAction("paywall", "tonight"), {
    kind: "paywall", route: { pathname: "/plus", params: { feature: "tonight" } },
  });
  assert.deepEqual(resolvePlusAction("error", "tonight"), {
    kind: "paywall", route: { pathname: "/plus", params: { feature: "tonight", unavailable: "1" } },
  });
  assert.deepEqual(resolvePlusAction("allow", "tonight"), { kind: "allow" });
  assert.deepEqual(resolvePlusAction("loading", "tonight"), { kind: "wait" });
});

test("paywall dismiss uses back navigation and has a safe Home fallback", () => {
  let action = "";
  dismissPlusPaywall(() => true, () => { action = "back"; }, () => { action = "replace"; });
  assert.equal(action, "back");
  dismissPlusPaywall(() => false, () => { action = "back"; }, path => { action = path; });
  assert.equal(action, "/(tabs)/discover");
});
