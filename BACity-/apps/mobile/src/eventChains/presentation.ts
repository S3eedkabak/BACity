import type { EventChainAlternative } from "../api/eventChains";
import type { PlusGateDecision } from "../plus/policy";

export type EventChainsViewState = "guarding" | "loading" | "error" | "empty" | "results";

export function resolveEventChainsView(
  gate: PlusGateDecision,
  pending: boolean,
  failed: boolean,
  chainCount: number,
): EventChainsViewState {
  if (gate !== "allow") return "guarding";
  if (pending) return "loading";
  if (failed) return "error";
  return chainCount === 0 ? "empty" : "results";
}

export function isValidRenderedChain(chain: EventChainAlternative, anchorId: string) {
  const anchors = chain.items.filter(item => item.is_anchor && item.event.id === anchorId);
  const relations = chain.items.map(item => item.relation);
  const anchorIndex = relations.indexOf("anchor");
  return anchors.length === 1 && anchorIndex >= 0
    && relations.slice(0, anchorIndex).every(relation => relation === "before")
    && relations.slice(anchorIndex + 1).every(relation => relation === "after");
}

export function eventChainsRoute(anchorEventId: string) {
  return { pathname: "/event-chains" as const, params: { anchorEventId } };
}

export function eventDetailRoute(eventId: string) {
  return `/event/${eventId}` as const;
}
