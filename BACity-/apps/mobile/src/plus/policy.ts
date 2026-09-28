export const PLUS_FEATURES = {
  tonight: "Tonight / Right Now",
  event_chains: "Event Chains",
  build_my_evening: "Build My Evening",
  weekend_generator: "Weekend Generator",
  group_match: "Group Match & Voting",
  area_watch: "Area Watch",
} as const;

export type PlusFeature = keyof typeof PLUS_FEATURES;
export type PlusGateDecision = "allow" | "paywall" | "loading" | "error";

export interface PlusAccessSnapshot {
  authenticated: boolean;
  pending: boolean;
  failed: boolean;
  active: boolean;
}

export function resolvePlusGate(snapshot: PlusAccessSnapshot): PlusGateDecision {
  if (!snapshot.authenticated) return "paywall";
  if (snapshot.pending) return "loading";
  if (snapshot.failed) return "error";
  return snapshot.active ? "allow" : "paywall";
}

export function isPlusFeature(value: string | string[] | undefined): value is PlusFeature {
  return typeof value === "string" && value in PLUS_FEATURES;
}

export function plusPaywallRoute(feature: PlusFeature, unavailable = false) {
  return {
    pathname: "/plus" as const,
    params: { feature, ...(unavailable ? { unavailable: "1" } : {}) },
  };
}

export function resolvePlusAction(decision: PlusGateDecision, feature: PlusFeature) {
  if (decision === "allow") return { kind: "allow" as const };
  if (decision === "loading") return { kind: "wait" as const };
  return {
    kind: "paywall" as const,
    route: plusPaywallRoute(feature, decision === "error"),
  };
}

export function dismissPlusPaywall(
  canGoBack: () => boolean,
  back: () => void,
  replace: (path: "/(tabs)/discover") => void,
) {
  if (canGoBack()) back();
  else replace("/(tabs)/discover");
}
