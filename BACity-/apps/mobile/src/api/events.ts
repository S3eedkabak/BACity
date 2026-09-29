import { apiRequest } from "./client";
import { EventListParams, EventListResponse, EventOut } from "../types/event";

export interface EventViewportBounds {
  min_lat: number;
  max_lat: number;
  min_lng: number;
  max_lng: number;
}

export function listEvents(params: EventListParams = {}): Promise<EventListResponse> {
  return apiRequest<EventListResponse>("/events", { params: params as Record<string, any> });
}

export function getEvent(id: string): Promise<EventOut> {
  return apiRequest<EventOut>(`/events/${id}`);
}

export function searchEvents(q: string, limit = 20): Promise<EventOut[]> {
  return apiRequest<EventOut[]>("/events/search", { params: { q, limit } });
}

export function nearbyEvents(lat: number, lng: number, radius_km = 5, limit = 50): Promise<EventOut[]> {
  return apiRequest<EventOut[]>("/events/nearby", { params: { lat, lng, radius_km, limit } });
}

export function eventsInViewport(bounds: EventViewportBounds, limit = 500): Promise<EventOut[]> {
  return apiRequest<EventOut[]>("/events/viewport", { params: { ...bounds, limit } });
}

export function saveEvent(id: string): Promise<{ event_id: string; saved: boolean }> {
  return apiRequest(`/events/${id}/save`, { method: "POST", auth: true });
}

export function unsaveEvent(id: string): Promise<{ event_id: string; saved: boolean }> {
  return apiRequest(`/events/${id}/save`, { method: "DELETE", auth: true });
}

export function getSavedEvents(): Promise<EventOut[]> {
  return apiRequest<EventOut[]>("/users/me/saved-events", { auth: true });
}
