import { apiRequest } from "./client";

export interface ConsumerBillingStatus {
  billing_enabled: boolean;
  plus_active: boolean;
  management_channel: "web" | "app_store" | "play_store" | "support" | null;
  provider: "stripe" | null;
  subscription_status: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  portal_available: boolean;
  checkout_available: boolean;
}

export const getConsumerBillingStatus = () =>
  apiRequest<ConsumerBillingStatus>("/billing/consumer/status", { auth: true });
export const createConsumerCheckout = () =>
  apiRequest<{ url: string }>("/billing/consumer/checkout", { method: "POST", auth: true });
export const createConsumerPortal = () =>
  apiRequest<{ url: string }>("/billing/consumer/portal", { method: "POST", auth: true });
export const reconcileConsumerBilling = () =>
  apiRequest<{ active: boolean; expires_at: string | null; management_channel: string | null }>(
    "/billing/consumer/reconcile", { method: "POST", auth: true },
  );
