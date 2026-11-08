import { apiRequest } from "./client";
import { EventOut } from "../types/event";

export interface RecommendationItem {
  event: EventOut;
  reasons: string[];
  saved: boolean;
}

export function getRecommendations(params: {
  offset: number;
  limit: number;
  latitude?: number;
  longitude?: number;
}): Promise<RecommendationItem[]> {
  return apiRequest<RecommendationItem[]>("/recommendations/query", {
    method: "POST",
    auth: true,
    body: params,
  });
}
