export interface PlayProduct {
  productId: string;
  localizedPrice: string;
  billingPeriod: string;
  offerToken: string;
}

export type PlayPurchase = { productId: string; purchaseToken: string };
export type PurchaseSubscription = { remove(): void };

export async function connectPlayBilling(): Promise<boolean> { return false; }
export async function disconnectPlayBilling(): Promise<void> {}
export function configurePlayBilling(_productId: string, _basePlanId: string | null,
                                     _accountId: string): void {}
export async function loadPlayProduct(_productId: string, _basePlanId: string | null,
                                      _accountId: string): Promise<PlayProduct | null> { return null; }
export async function startPlayPurchase(): Promise<void> { throw new Error("Billing unavailable"); }
export async function restorePlayPurchases(): Promise<PlayPurchase[]> { return []; }
export function listenForPlayPurchases(_onPurchase: (purchase: PlayPurchase) => void,
                                       _onError: (error: { code?: string }) => void): PurchaseSubscription {
  return { remove() {} };
}
