import {
  endConnection, getAvailablePurchases, getSubscriptions, initConnection,
  purchaseErrorListener, purchaseUpdatedListener, requestSubscription,
  type PurchaseError, type SubscriptionAndroid,
} from "react-native-iap";
import type { PlayProduct, PlayPurchase, PurchaseSubscription } from "./playBilling";

let configuredProductId: string | null = null;
let configuredBasePlanId: string | null = null;
let configuredAccountId: string | null = null;
let selected: PlayProduct | null = null;
let connected = false;

export function configurePlayBilling(productId: string, basePlanId: string | null, accountId: string): void {
  if (configuredAccountId !== accountId || configuredProductId !== productId || configuredBasePlanId !== basePlanId) selected = null;
  configuredProductId = productId;
  configuredBasePlanId = basePlanId;
  configuredAccountId = accountId;
}

export async function connectPlayBilling(): Promise<boolean> {
  if (connected) return true;
  connected = await initConnection();
  return connected;
}

export async function disconnectPlayBilling(): Promise<void> {
  selected = null;
  configuredAccountId = null;
  if (connected) await endConnection();
  connected = false;
}

export async function loadPlayProduct(productId: string, basePlanId: string | null,
                                      accountId: string): Promise<PlayProduct | null> {
  configurePlayBilling(productId, basePlanId, accountId);
  const products = await getSubscriptions({ skus: [productId] });
  if (configuredAccountId !== accountId || configuredProductId !== productId || configuredBasePlanId !== basePlanId) return null;
  const product = products.find(item => item.productId === productId) as SubscriptionAndroid | undefined;
  if (!product || product.platform !== "android") return null;
  // V1 uses the base plan, not introductory/trial offers whose first price
  // phase could conceal the recurring price shown on this paywall.
  const offer = product.subscriptionOfferDetails.find(item => (!basePlanId || item.basePlanId === basePlanId) && !item.offerId);
  const phase = offer?.pricingPhases.pricingPhaseList.find(item => item.recurrenceMode === 1);
  if (!offer || !phase) return null;
  selected = {
    productId,
    offerToken: offer.offerToken,
    localizedPrice: phase.formattedPrice,
    billingPeriod: phase.billingPeriod,
  };
  return selected;
}

export async function startPlayPurchase(): Promise<void> {
  if (!selected || !configuredProductId || !configuredAccountId) throw new Error("Billing unavailable");
  await requestSubscription({
    subscriptionOffers: [{ sku: configuredProductId, offerToken: selected.offerToken }],
    obfuscatedAccountIdAndroid: configuredAccountId,
  });
}

export async function restorePlayPurchases(): Promise<PlayPurchase[]> {
  if (!configuredProductId) return [];
  const purchases = await getAvailablePurchases();
  return purchases
    .filter(item => item.productId === configuredProductId && typeof item.purchaseToken === "string")
    .slice(0, 10)
    .map(item => ({ productId: item.productId, purchaseToken: item.purchaseToken! }));
}

export function listenForPlayPurchases(onPurchase: (purchase: PlayPurchase) => void,
                                       onError: (error: PurchaseError) => void): PurchaseSubscription {
  const updated = purchaseUpdatedListener(purchase => {
    if (purchase.productId === configuredProductId && purchase.purchaseToken) {
      onPurchase({ productId: purchase.productId, purchaseToken: purchase.purchaseToken });
    }
  });
  const failed = purchaseErrorListener(onError);
  return { remove() { updated.remove(); failed.remove(); } };
}
