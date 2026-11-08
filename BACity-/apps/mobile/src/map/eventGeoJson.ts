import type { EventOut } from "../types/event";

export type LocatedEvent = EventOut & { latitude: number; longitude: number };

export function hasValidMapCoordinates(event: EventOut): event is LocatedEvent {
  return (
    typeof event.latitude === "number" &&
    Number.isFinite(event.latitude) &&
    event.latitude >= -90 &&
    event.latitude <= 90 &&
    typeof event.longitude === "number" &&
    Number.isFinite(event.longitude) &&
    event.longitude >= -180 &&
    event.longitude <= 180
  );
}

export function buildEventFeatureCollection(
  events: LocatedEvent[],
  isNearby: (event: LocatedEvent) => boolean,
): GeoJSON.FeatureCollection<GeoJSON.Point, { id: string; title: string; nearby: boolean }> {
  return {
    type: "FeatureCollection",
    features: events.map((event) => ({
      type: "Feature",
      id: event.id,
      geometry: {
        type: "Point",
        coordinates: [event.longitude, event.latitude],
      },
      properties: {
        id: event.id,
        title: event.title,
        nearby: isNearby(event),
      },
    })),
  };
}
