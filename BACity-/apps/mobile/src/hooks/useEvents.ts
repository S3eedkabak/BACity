/**
 * TanStack Query hooks wrapping src/api/events.ts. Screens should use
 * these rather than calling the API module directly, so caching/refetch/
 * invalidation stay consistent across Home/Explore/Saved.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as eventsApi from "../api/events";
import { EventListParams } from "../types/event";
import { useAuthStore } from "../store/authStore";

export function useEvents(params: EventListParams = {}) {
  return useQuery({
    queryKey: ["events", params],
    queryFn: () => eventsApi.listEvents(params),
    staleTime: 60_000,
  });
}

export function useEvent(id: string | undefined) {
  return useQuery({
    queryKey: ["event", id],
    queryFn: () => eventsApi.getEvent(id as string),
    enabled: !!id,
  });
}

export function useSearchEvents(query: string) {
  return useQuery({
    queryKey: ["events-search", query],
    queryFn: () => eventsApi.searchEvents(query),
    enabled: query.trim().length > 0,
  });
}

export function useNearbyEvents(lat?: number, lng?: number, radiusKm = 5) {
  return useQuery({
    queryKey: ["events-nearby", lat, lng, radiusKm],
    queryFn: () => eventsApi.nearbyEvents(lat as number, lng as number, radiusKm),
    enabled: lat !== undefined && lng !== undefined,
  });
}

export function useSavedEvents() {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: ["saved-events"],
    queryFn: eventsApi.getSavedEvents,
    enabled: !!token,
  });
}

export function useToggleSaveEvent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, saved }: { id: string; saved: boolean }) =>
      saved ? eventsApi.unsaveEvent(id) : eventsApi.saveEvent(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["saved-events"] });
    },
  });
}