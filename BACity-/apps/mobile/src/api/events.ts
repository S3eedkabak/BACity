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

export function mapClusters(bounds: EventViewportBounds, zoom: number, filters: import('../map/area').MapFilters = {}, signal?: AbortSignal) {
  return apiRequest<import('../map/area').ClusterData>('/events/map/clusters', {params:{...bounds,zoom,...filters},signal});
}
export interface AreaPage {name:string;total:number;items:EventOut[];has_more:boolean;next_cursor:string|null;refreshed:boolean;}
export function areaEvents(area_token:string, filters:import('../map/area').MapFilters, cursor?:string, signal?:AbortSignal) {
  return apiRequest<AreaPage>('/events/map/area',{params:{area_token,...filters,override_filters:true,cursor,limit:30},signal});
}

export interface DistrictData extends GeoJSON.FeatureCollection<GeoJSON.Polygon|GeoJSON.MultiPolygon,{id:string;name:string;count:number;area_token:string;label_coordinates:[number,number]}> {source:string;outside_districts:number;}
export function mapDistricts(filters:import('../map/area').MapFilters={},signal?:AbortSignal) {
  return apiRequest<DistrictData>('/events/map/districts',{params:{...filters},signal});
}

export interface OccurrencePage {total:number;next_offset:number|null;items:{id:string;source_url:string;start_time:string;end_time:string|null;status:string;start_precision:'date'|'time'}[];}
export function eventOccurrences(id:string,offset=0,signal?:AbortSignal) {
  return apiRequest<OccurrencePage>(`/events/${id}/occurrences`,{params:{offset,limit:10},signal});
}
