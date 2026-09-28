import { apiRequest } from "./client";
import { EventCategory, EventOut } from "../types/event";

export type EveningStrategy = "best_match" | "relaxed" | "something_different";

export interface EveningPlanRequest {
  date: string;
  start_time: string;
  end_time: string;
  categories: EventCategory[];
  latitude?: number;
  longitude?: number;
}

export interface EveningPlanItem {
  event: EventOut;
  reasons: string[];
  location_confidence: "nearby" | "distance_buffered" | "location_unknown" | null;
}

export interface EveningPlanAlternative {
  id: string;
  strategy: EveningStrategy;
  explanation: string;
  limited: boolean;
  items: EveningPlanItem[];
}

export interface EveningPlanResponse {
  timezone: string;
  window_start: string;
  window_end: string;
  location_used: boolean;
  plans: EveningPlanAlternative[];
}

export function generateEveningPlans(payload: EveningPlanRequest) {
  return apiRequest<EveningPlanResponse>("/recommendations/evening-plan", {
    method: "POST",
    auth: true,
    body: payload,
  });
}
