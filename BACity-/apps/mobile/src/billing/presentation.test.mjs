import test from "node:test";
import assert from "node:assert/strict";
import { billingMessage, billingReturnState, canShowWebPurchase } from "./presentation.ts";

test("Stripe purchase controls are web-only and server-enabled", () => {
  assert.equal(canShowWebPurchase("web", true, true), true);
  assert.equal(canShowWebPurchase("android", true, true), false);
  assert.equal(canShowWebPurchase("ios", true, true), false);
  assert.equal(canShowWebPurchase("web", false, true), false);
  assert.equal(canShowWebPurchase("web", true, false), false);
});

test("expired or active accounts remain server-controlled", () => {
  assert.equal(canShowWebPurchase("web", true, true), true);
  assert.equal(canShowWebPurchase("web", true, false), false);
  assert.match(billingMessage("success", false, false), /not confirmed/);
});

test("success is verifying and never an instant local entitlement", () => {
  assert.equal(billingReturnState("success"), "success");
  assert.match(billingMessage("success", true, false), /Verifying/);
  assert.match(billingMessage("success", false, false), /not confirmed/);
  assert.match(billingMessage("success", false, true), /verified/);
});

test("cancel return leaves access unchanged", () => {
  assert.equal(billingReturnState("cancelled"), "cancelled");
  assert.match(billingMessage("cancelled", false, false), /No BACity\+ access was changed/);
});
