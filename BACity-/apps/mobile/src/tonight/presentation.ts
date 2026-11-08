import type { TonightClassification, TonightItem } from "../api/tonight";
import type { PlusGateDecision } from "../plus/policy";

export type TonightViewState = "guarding" | "loading" | "error" | "empty" | "results";

export const TONIGHT_SECTION_LABELS: Record<TonightClassification, string> = {
  happening_now: "Happening now",
  starting_soon: "Starting soon",
  later_tonight: "Later tonight",
};

export function resolveTonightView(
  gate: PlusGateDecision,
  pending: boolean,
  failed: boolean,
  itemCount: number,
): TonightViewState {
  if (gate !== "allow") return "guarding";
  if (pending) return "loading";
  if (failed) return "error";
  return itemCount === 0 ? "empty" : "results";
}

export function groupTonightItems(items: TonightItem[]) {
  return (Object.keys(TONIGHT_SECTION_LABELS) as TonightClassification[])
    .map(classification => ({
      classification,
      title: TONIGHT_SECTION_LABELS[classification],
      data: items.filter(item => item.classification === classification),
    }))
    .filter(section => section.data.length > 0);
}

export function tonightLocationCopy(locationUsed: boolean) {
  return locationUsed ? "Using an approximate current location" : "Showing citywide Bratislava picks";
}
