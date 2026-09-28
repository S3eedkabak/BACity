import { apiRequest } from "./client";

export interface EntitlementState {
  active: boolean;
  expires_at: string | null;
  management_channel: "web" | "app_store" | "play_store" | "support" | null;
}

export interface Entitlements {
  bacity_plus: EntitlementState;
}

export function getEntitlements(): Promise<Entitlements> {
  return apiRequest<Entitlements>("/users/me/entitlements", { auth: true });
}
