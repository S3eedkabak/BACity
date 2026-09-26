import AsyncStorage from "@react-native-async-storage/async-storage";
import type { Utility, UtilityBounds } from "../api/utilities";
import type { EventOut } from "../types/event";

const STORAGE_KEY = "@bacity/map-snapshot-v1";
const MAX_EVENTS = 200;
const MAX_UTILITIES = 1_000;
const WRITE_DELAY_MS = 750;

export type MapSnapshot = {
  savedAt: number;
  events: EventOut[];
  utilities: Utility[];
};

let memorySnapshot: MapSnapshot | null = null;
let loadPromise: Promise<MapSnapshot> | null = null;
let writeTimer: ReturnType<typeof setTimeout> | null = null;
let eventsUpdated = false;
let utilitiesUpdated = false;

const emptySnapshot = (): MapSnapshot => ({ savedAt: 0, events: [], utilities: [] });

function isSnapshot(value: unknown): value is MapSnapshot {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<MapSnapshot>;
  return typeof candidate.savedAt === "number" && Array.isArray(candidate.events) && Array.isArray(candidate.utilities);
}

export async function loadMapSnapshot(): Promise<MapSnapshot> {
  if (memorySnapshot) return memorySnapshot;
  if (loadPromise) return loadPromise;

  loadPromise = AsyncStorage.getItem(STORAGE_KEY)
    .then((raw) => {
      if (!raw) return emptySnapshot();
      const parsed: unknown = JSON.parse(raw);
      return isSnapshot(parsed) ? parsed : emptySnapshot();
    })
    .catch(() => emptySnapshot())
    .then((snapshot) => {
      memorySnapshot = memorySnapshot ? {
        savedAt: Math.max(snapshot.savedAt, memorySnapshot.savedAt),
        events: eventsUpdated ? memorySnapshot.events : snapshot.events,
        utilities: utilitiesUpdated ? memorySnapshot.utilities : snapshot.utilities,
      } : snapshot;
      return memorySnapshot;
    });

  return loadPromise;
}

function scheduleWrite() {
  if (writeTimer) clearTimeout(writeTimer);
  writeTimer = setTimeout(() => {
    writeTimer = null;
    void loadMapSnapshot().then((snapshot) =>
      AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(memorySnapshot ?? snapshot))
    ).catch(() => undefined);
  }, WRITE_DELAY_MS);
}

export function updateMapSnapshot(update: Partial<Pick<MapSnapshot, "events" | "utilities">>): MapSnapshot {
  const current = memorySnapshot ?? emptySnapshot();
  if (update.events !== undefined) eventsUpdated = true;
  if (update.utilities !== undefined) utilitiesUpdated = true;
  memorySnapshot = {
    savedAt: Date.now(),
    events: (update.events ?? current.events).slice(0, MAX_EVENTS),
    utilities: (update.utilities ?? current.utilities).slice(0, MAX_UTILITIES),
  };
  scheduleWrite();
  return memorySnapshot;
}

export function mergeViewportUtilities(
  cached: Utility[],
  fresh: Utility[],
  bounds: UtilityBounds,
): Utility[] {
  const freshIds = new Set(fresh.map((item) => item.id));
  const retained = cached.filter((item) => {
    const inside =
      item.latitude >= bounds.min_lat && item.latitude <= bounds.max_lat &&
      item.longitude >= bounds.min_lng && item.longitude <= bounds.max_lng;
    return !inside || freshIds.has(item.id);
  });
  const merged = new Map(retained.map((item) => [item.id, item]));
  for (const item of fresh) merged.set(item.id, item);
  return Array.from(merged.values()).slice(-MAX_UTILITIES);
}

export function expandAndSnapBounds(bounds: UtilityBounds): UtilityBounds {
  const latitudePadding = (bounds.max_lat - bounds.min_lat) * 0.2;
  const longitudePadding = (bounds.max_lng - bounds.min_lng) * 0.2;
  const grid = 0.0025;
  return {
    min_lat: Math.floor((bounds.min_lat - latitudePadding) / grid) * grid,
    max_lat: Math.ceil((bounds.max_lat + latitudePadding) / grid) * grid,
    min_lng: Math.floor((bounds.min_lng - longitudePadding) / grid) * grid,
    max_lng: Math.ceil((bounds.max_lng + longitudePadding) / grid) * grid,
  };
}

export function containsBounds(container: UtilityBounds, candidate: UtilityBounds): boolean {
  return candidate.min_lat >= container.min_lat && candidate.max_lat <= container.max_lat &&
    candidate.min_lng >= container.min_lng && candidate.max_lng <= container.max_lng;
}

export function boundsKey(bounds: UtilityBounds): string {
  return [bounds.min_lat, bounds.max_lat, bounds.min_lng, bounds.max_lng]
    .map((value) => value.toFixed(4))
    .join(":");
}
