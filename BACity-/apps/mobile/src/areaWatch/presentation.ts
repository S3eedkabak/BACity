import type { PlusGateDecision } from "../plus/policy";

export type AreaWatchView = "loading" | "paywall" | "error" | "empty" | "content";

export function resolveAreaWatchView(gate: PlusGateDecision, failed: boolean, count: number): AreaWatchView {
  if (gate === "loading") return "loading";
  if (gate !== "allow") return "paywall";
  if (failed) return "error";
  return count ? "content" : "empty";
}

export function validWatchCoordinates(latitude: number, longitude: number) {
  return Number.isFinite(latitude) && Number.isFinite(longitude) && latitude >= 48 && latitude <= 48.35 && longitude >= 16.9 && longitude <= 17.35;
}

export function areaWatchRoute(id: string) { return `/area-watch/${id}` as const; }
export function areaWatchEventRoute(id: string) { return `/event/${id}` as const; }
export function totalUnseen(watches: { unseen_count: number }[]) { return watches.reduce((sum, watch) => sum + watch.unseen_count, 0); }
