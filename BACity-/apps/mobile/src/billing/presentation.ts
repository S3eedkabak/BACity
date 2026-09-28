export type BillingReturn = "success" | "cancelled" | null;

export function billingReturnState(value: string | string[] | undefined): BillingReturn {
  return value === "success" || value === "cancelled" ? value : null;
}

export function canShowWebPurchase(platform: string, enabled: boolean, checkoutAvailable: boolean) {
  return platform === "web" && enabled && checkoutAvailable;
}

export function billingMessage(state: BillingReturn, verifying: boolean, active: boolean) {
  if (state === "cancelled") return "Checkout was cancelled. No BACity+ access was changed.";
  if (state === "success" && verifying) return "Payment received. Verifying your subscription…";
  if (state === "success" && active) return "Your verified BACity+ subscription is active.";
  if (state === "success") return "Stripe has not confirmed an active subscription yet. Try again shortly.";
  return null;
}
