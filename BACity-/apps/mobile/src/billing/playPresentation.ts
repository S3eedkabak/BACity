export type PlayUiState = "idle" | "loading" | "pending" | "cancelled" | "verifying" | "verified" | "failed" | "restoring" | "nothing";

export function canStartPlayPurchase(platform: string, configured: boolean, productLoaded: boolean,
                                     plusActive: boolean, activeOtherProvider: boolean) {
  return platform === "android" && configured && productLoaded && !plusActive && !activeOtherProvider;
}

export function playStateMessage(state: PlayUiState) {
  return {
    idle: null,
    loading: "Loading Google Play subscription…",
    pending: "Google Play is processing this purchase.",
    cancelled: "Purchase cancelled. Your access was not changed.",
    verifying: "Verifying purchase with Google Play…",
    verified: "Your verified BACity+ subscription is active.",
    failed: "BACity could not verify this purchase. Retry Restore Purchases shortly.",
    restoring: "Checking Google Play purchases…",
    nothing: "No BACity+ purchase was found for this Google Play account.",
  }[state];
}

export function shouldRefreshEntitlements(serverVerifiedActive: boolean) {
  return serverVerifiedActive;
}
