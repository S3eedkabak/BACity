// Mirrors services/api/app/schemas/event.py — keep in sync with the backend.

export type EventCategory =
  | "Music" | "Nightlife" | "Culture" | "Arts" | "Theatre" | "Sports"
  | "Food & Drink" | "Education" | "Workshops" | "Community" | "Networking"
  | "Family" | "Markets" | "Festivals" | "Student" | "Technology"
  | "Comedy" | "Exhibitions" | "Other";

export type EventStatus = "fresh" | "stale" | "expired" | "removed" | "cancelled";

export interface VenueSummary {
  id: string;
  name: string;
  address: string | null;
  latitude: number | null;
  longitude: number | null;
}

export interface EventOut {
  id: string;
  title: string;
  description: string | null;
  start_time: string; // ISO 8601
  end_time: string | null;
  timezone: string;
  address: string | null;
  latitude: number | null;
  longitude: number | null;
  category: EventCategory;
  tags: string[];
  price: number | null; // null = unknown, 0 = free
  currency: string | null;
  image_url: string | null;
  source_url: string;
  language: string;
  status: EventStatus;
  extraction_confidence: number;
  source_reliability: number;
  venue: VenueSummary | null;
  created_at: string;
  updated_at: string;
}

export interface EventListResponse {
  total: number;
  items: EventOut[];
}

export interface EventListParams {
  category?: string;
  tag?: string;
  free_only?: boolean;
  starts_after?: string;
  starts_before?: string;
  limit?: number;
  offset?: number;
}