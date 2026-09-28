import { apiRequest } from "./client";
import type { EventCategory, EventOut } from "../types/event";

export type WatchRadius = 1 | 2 | 5;

export interface AreaWatchSummary {
  id: string; name: string; radius_km: number; categories: EventCategory[];
  active: boolean; locked: boolean; unseen_count: number;
}

export interface AreaWatch extends AreaWatchSummary {
  center_latitude: number; center_longitude: number; last_viewed_at: string | null;
  created_at: string; updated_at: string;
}

export interface AreaWatchEvent {
  event: EventOut; discovered_at: string; unseen: boolean; explanations: string[];
}

export interface AreaWatchFeed {
  items: AreaWatchEvent[]; next_cursor: string | null; response_watermark: string;
  unseen_count: number; lookback_days: number;
}

export interface AreaWatchInput {
  name: string; center_latitude: number; center_longitude: number;
  radius_km: WatchRadius; categories: EventCategory[];
}

export const areaWatchesApi = {
  list: () => apiRequest<AreaWatchSummary[]>("/area-watches", { auth: true }),
  get: (id: string) => apiRequest<AreaWatch>(`/area-watches/${id}`, { auth: true }),
  create: (payload: AreaWatchInput) => apiRequest<AreaWatch>("/area-watches", { method: "POST", auth: true, body: JSON.stringify(payload) }),
  update: (id: string, payload: Partial<AreaWatchInput> & { active?: boolean }) => apiRequest<AreaWatch>(`/area-watches/${id}`, { method: "PATCH", auth: true, body: JSON.stringify(payload) }),
  remove: (id: string) => apiRequest<{ deleted: boolean }>(`/area-watches/${id}`, { method: "DELETE", auth: true }),
  events: (id: string, cursor?: string | null) => apiRequest<AreaWatchFeed>(`/area-watches/${id}/events`, { auth: true, params: { limit: 20, ...(cursor ? { cursor } : {}) } }),
  seen: (id: string, watermark: string) => apiRequest<AreaWatch>(`/area-watches/${id}/seen`, { method: "POST", auth: true, body: JSON.stringify({ watermark }) }),
};
