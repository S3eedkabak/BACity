import { apiRequest } from "./client";

export interface GooglePlayBillingConfig {
  configured: boolean;
  package_name: string | null;
  product_id: string | null;
  base_plan_id: string | null;
  obfuscated_account_id: string | null;
  plus_active: boolean;
  management_channel: "web" | "app_store" | "play_store" | "support" | null;
  active_paid_other_provider: boolean;
  subscription_status: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
}

export interface GooglePlayVerification {
  active: boolean;
  expires_at: string | null;
  management_channel: string | null;
  subscription_status: string;
  cancel_at_period_end: boolean;
}

export const getGooglePlayBillingConfig = () =>
  apiRequest<GooglePlayBillingConfig>("/billing/google-play/config", { auth: true });

export const verifyGooglePlayPurchase = (purchaseToken: string, productId: string) =>
  apiRequest<GooglePlayVerification>("/billing/google-play/verify", {
    method: "POST", auth: true, body: { purchase_token: purchaseToken, product_id: productId },
  });

export const reconcileGooglePlayBilling = () =>
  apiRequest<{ active: boolean; expires_at: string | null; management_channel: string | null; reconciled: number }>(
    "/billing/google-play/reconcile", { method: "POST", auth: true },
  );
