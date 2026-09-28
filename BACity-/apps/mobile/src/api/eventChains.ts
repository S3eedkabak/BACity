import { apiRequest } from "./client";
import { EventOut } from "../types/event";

export type EventChainMode = "before" | "after" | "full";
export type EventChainRelation = "before" | "anchor" | "after";

export interface EventChainItem {
  event: EventOut;
  relation: EventChainRelation;
  is_anchor: boolean;
  reasons: string[];
  location_confidence: "nearby" | "distance_buffered" | "location_unknown" | null;
}

export interface EventChainAlternative {
  id: string;
  items: EventChainItem[];
}

export interface EventChainResponse {
  anchor_event_id: string;
  mode: EventChainMode;
  chains: EventChainAlternative[];
}

export function getEventChains(anchorEventId: string, mode: EventChainMode) {
  return apiRequest<EventChainResponse>("/recommendations/event-chain", {
    method: "POST",
    auth: true,
    body: { anchor_event_id: anchorEventId, mode },
  });
}
