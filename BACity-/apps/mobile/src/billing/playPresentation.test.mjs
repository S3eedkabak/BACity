import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { canStartPlayPurchase, playStateMessage, shouldRefreshEntitlements } from "./playPresentation.ts";

test("Android purchase requires configuration, loaded product and no existing entitlement", () => {
  assert.equal(canStartPlayPurchase("android", true, true, false, false), true);
  assert.equal(canStartPlayPurchase("web", true, true, false, false), false);
  assert.equal(canStartPlayPurchase("ios", true, true, false, false), false);
  assert.equal(canStartPlayPurchase("android", false, true, false, false), false);
  assert.equal(canStartPlayPurchase("android", true, false, false, false), false);
  assert.equal(canStartPlayPurchase("android", true, true, true, false), false);
  assert.equal(canStartPlayPurchase("android", true, true, false, true), false);
});

test("purchase, cancellation, verification and restore states are explicit", () => {
  assert.match(playStateMessage("loading"), /Loading/);
  assert.match(playStateMessage("pending"), /processing/);
  assert.match(playStateMessage("cancelled"), /not changed/);
  assert.match(playStateMessage("verifying"), /Verifying/);
  assert.match(playStateMessage("verified"), /verified/);
  assert.match(playStateMessage("failed"), /could not verify/);
  assert.match(playStateMessage("restoring"), /Checking/);
  assert.match(playStateMessage("nothing"), /No BACity\+ purchase/);
});

test("local purchase success never authorizes entitlement cache", () => {
  assert.equal(shouldRefreshEntitlements(false), false);
  assert.equal(shouldRefreshEntitlements(true), true);
});

test("Google purchase API uses central object serialization and account-scoped refresh", async () => {
  const api = await readFile(new URL("../api/googlePlayBilling.ts", import.meta.url), "utf8");
  const paywall = await readFile(new URL("../../app/plus.tsx", import.meta.url), "utf8");
  assert.doesNotMatch(api, /JSON\.stringify/);
  assert.match(api, /body: \{ purchase_token: purchaseToken, product_id: productId \}/);
  assert.match(paywall, /await entitlement\.refresh\(\)/);
  assert.doesNotMatch(paywall, /setQueryData\([^)]*active/);
});
