import type { EventViewportBounds } from "../api/events";
import type { EventOut } from "../types/event";

export const MAX_CACHED_MAP_EVENTS = 1_000;
export const EVENT_VIEWPORT_LIMIT = 500;

export function mergeViewportEvents(
  cached: EventOut[],
  fresh: EventOut[],
  bounds: EventViewportBounds,
): EventOut[] {
  const freshIds = new Set(fresh.map((item) => item.id));
  const responseIsComplete = fresh.length < EVENT_VIEWPORT_LIMIT;
  const retained = cached.filter((item) => {
    const inside =
      item.latitude != null && item.longitude != null &&
      item.latitude >= bounds.min_lat && item.latitude <= bounds.max_lat &&
      item.longitude >= bounds.min_lng && item.longitude <= bounds.max_lng;
    return !responseIsComplete || !inside || freshIds.has(item.id);
  });
  const merged = new Map(retained.map((item) => [item.id, item]));
  for (const item of fresh) merged.set(item.id, item);
  return Array.from(merged.values()).slice(-MAX_CACHED_MAP_EVENTS);
}
