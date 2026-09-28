import { apiRequest } from "./client";
import { EventOut } from "../types/event";

export type TonightClassification = "happening_now" | "starting_soon" | "later_tonight";

export interface TonightItem {
  event: EventOut;
  classification: TonightClassification;
  reasons: string[];
  saved: boolean;
}

export interface TonightResponse {
  timezone: string;
  window_start: string;
  window_end: string;
  location_used: boolean;
  items: TonightItem[];
}

export function getTonightRecommendations(coordinates: { latitude: number; longitude: number } | null) {
  return apiRequest<TonightResponse>("/recommendations/tonight", {
    method: "POST",
    auth: true,
    body: coordinates ?? {},
  });
}
