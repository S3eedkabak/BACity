import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";
import { serializeRequestBody } from "../api/requestBody.ts";

async function moduleWithMocks(path, dependencies) {
  const source = await readFile(new URL(path, import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
  const exports = {};
  vm.runInNewContext(compiled, { exports, require: name => dependencies[name], console });
  return exports;
}

test("actual Android adapter loads base-plan recurring price, binds purchase, restores and isolates accounts", async () => {
  let request;
  const adapter = await moduleWithMocks("./playBilling.android.ts", {
    "react-native-iap": {
      initConnection: async () => true, endConnection: async () => {},
      getSubscriptions: async () => [{ productId: "plus", platform: "android", subscriptionOfferDetails: [
        { basePlanId: "monthly", offerId: "trial", offerToken: "trial", pricingPhases: { pricingPhaseList: [{ recurrenceMode: 2, formattedPrice: "Free", billingPeriod: "P1W" }] } },
        { basePlanId: "monthly", offerId: null, offerToken: "base", pricingPhases: { pricingPhaseList: [{ recurrenceMode: 1, formattedPrice: "€4.50", billingPeriod: "P1M" }] } },
      ] }],
      requestSubscription: async value => { request = value; },
      getAvailablePurchases: async () => [{ productId: "plus", purchaseToken: "private-token" }, { productId: "other", purchaseToken: "other-token" }],
    },
  });
  assert.equal(await adapter.connectPlayBilling(), true);
  const product = await adapter.loadPlayProduct("plus", "monthly", "account-a");
  assert.equal(product.localizedPrice, "€4.50");
  assert.equal(product.billingPeriod, "P1M");
  await adapter.startPlayPurchase();
  assert.equal(request.obfuscatedAccountIdAndroid, "account-a");
  assert.equal(request.subscriptionOffers[0].offerToken, "base");
  assert.equal((await adapter.restorePlayPurchases()).length, 1);
  adapter.configurePlayBilling("plus", "monthly", "account-b");
  await assert.rejects(adapter.startPlayPurchase(), /unavailable/);
  await adapter.disconnectPlayBilling();
  await assert.rejects(adapter.startPlayPurchase(), /unavailable/);
});

test("actual purchase listeners forward token without locally authorizing access and remove both listeners", async () => {
  let updated, failed, received, error;
  let removed = 0;
  const adapter = await moduleWithMocks("./playBilling.android.ts", {
    "react-native-iap": {
      purchaseUpdatedListener: callback => { updated = callback; return { remove: () => removed++ }; },
      purchaseErrorListener: callback => { failed = callback; return { remove: () => removed++ }; },
    },
  });
  adapter.configurePlayBilling("plus", null, "account-a");
  const subscription = adapter.listenForPlayPurchases(value => { received = value; }, value => { error = value; });
  updated({ productId: "plus", purchaseToken: "private-token" });
  assert.equal(received.purchaseToken, "private-token");
  assert.equal(received.active, undefined);
  failed({ code: "E_USER_CANCELLED" });
  assert.equal(error.code, "E_USER_CANCELLED");
  subscription.remove();
  assert.equal(removed, 2);
});

test("actual Google API serializes verification once at central transport boundary", async () => {
  let outgoing;
  const api = await moduleWithMocks("../api/googlePlayBilling.ts", {
    "./client": { apiRequest: async (path, options) => { outgoing = { path, body: serializeRequestBody(options.body) }; return { active: false }; } },
  });
  await api.verifyGooglePlayPurchase("private-token", "plus");
  assert.equal(outgoing.path, "/billing/google-play/verify");
  assert.deepEqual(JSON.parse(outgoing.body), { purchase_token: "private-token", product_id: "plus" });
});
