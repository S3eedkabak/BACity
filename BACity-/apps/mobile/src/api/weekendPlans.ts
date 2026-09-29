import { apiRequest } from "./client";
import type { EventCategory, EventOut } from "../types/event";

export type WeekendMode = "saturday" | "sunday" | "weekend";
export type WeekendStrategy = "relaxed" | "culture_heavy" | "something_different";

export interface WeekendPlanRequest {
  weekend_start: string;
  mode: WeekendMode;
  categories: EventCategory[];
  latitude?: number;
  longitude?: number;
}

export interface WeekendPlanItem {
  event: EventOut;
  reasons: string[];
  location_confidence: "nearby" | "distance_buffered" | "location_unknown" | null;
}

export interface WeekendPlanDay {
  date: string;
  day: "Saturday" | "Sunday";
  window_start: string;
  window_end: string;
  limited: boolean;
  items: WeekendPlanItem[];
}

export interface WeekendPlanAlternative {
  id: string;
  strategy: WeekendStrategy;
  explanation: string;
  limited: boolean;
  days: WeekendPlanDay[];
}

export interface WeekendPlanResponse {
  timezone: string;
  weekend_start: string;
  mode: WeekendMode;
  location_used: boolean;
  plans: WeekendPlanAlternative[];
}

export function generateWeekendPlans(payload: WeekendPlanRequest) {
  return apiRequest<WeekendPlanResponse>("/recommendations/weekend-plan", {
    method: "POST",
    auth: true,
    body: payload,
  });
}
