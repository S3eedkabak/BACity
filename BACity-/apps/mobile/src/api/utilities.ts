import { apiRequest } from "./client";

export interface Utility {
  id: string;
  kind: string;
  name: string;
  latitude: number;
  longitude: number;
  address?: string | null;
  opening_hours?: string | null;
  free?: boolean | null;
  operational_status: "open" | "closed" | "out_of_order" | "unknown";
  confirmation_count: number;
  status_conflict: boolean;
  confidence_score: number;
  freshness_score: number;
  freshness_status: "current" | "recent" | "aging" | "stale" | "unknown";
}

export interface UtilityBounds {
  min_lat: number;
  max_lat: number;
  min_lng: number;
  max_lng: number;
}

export function utilitiesInViewport(bounds: UtilityBounds): Promise<Utility[]> {
  return apiRequest<Utility[]>("/community/utilities/viewport", {
    params: { ...bounds, kind: "toilet", limit: 500 },
  });
}

export function nearbyUtilities(latitude: number, longitude: number, radiusKm = 3): Promise<Utility[]> {
  return apiRequest<Utility[]>("/community/utilities/nearby", {
    params: { lat: latitude, lng: longitude, radius_km: radiusKm, kind: "toilet" },
  });
}
