/**
 * TanStack Query hooks wrapping src/api/events.ts. Screens should use
 * these rather than calling the API module directly, so caching/refetch/
 * invalidation stay consistent across Home/Explore/Saved.
 */
import { useCallback } from 'react';
import { useFocusEffect } from 'expo-router';
import { useIsFocused } from '@react-navigation/native';
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as eventsApi from "../api/events";
import { EventListParams, EventListResponse, EventOut } from "../types/event";
import { useAuthStore } from "../store/authStore";
import { createActionGate, applySaved } from '../interactions/policy';
import { withLoadingTestDelay } from '../loading/development';

export function useEvents(params: EventListParams = {}) {
  const focused=useIsFocused();
  const query=useQuery({
    queryKey: ["events", params],
    queryFn: () => eventsApi.listEvents(params),
    staleTime: 60_000,
    refetchInterval:focused?60_000:false,
  });
  useFocusEffect(useCallback(()=>{void query.refetch();},[query.refetch]));
  return query;
}

export function useEvent(id: string | undefined) {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: ["event", id],
    queryFn: () => withLoadingTestDelay(() => eventsApi.getEvent(id as string)),
    enabled: !!id,
    initialData: () => queryClient.getQueriesData<EventListResponse>({ queryKey: ['events'] })
      .flatMap(([, value]) => value?.items ?? []).find(event => event.id === id),
    initialDataUpdatedAt: 0,
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

const saveGates = new WeakMap<object, ReturnType<typeof createActionGate>>();
export function useToggleSaveEvent() {
  const queryClient = useQueryClient();
  let gate = saveGates.get(queryClient);
  if (!gate) { gate = createActionGate(); saveGates.set(queryClient, gate); }
  const mutation = useMutation({
    mutationKey: ['save-event'],
    mutationFn: async ({ id, saved, event, desiredSaved }: { id: string; saved: boolean; event?: EventOut; desiredSaved?: boolean }) => {
      await queryClient.cancelQueries({ queryKey: ['saved-events'] });
      const prior = queryClient.getQueryData<EventOut[]>(['saved-events']);
      const previousEvent = prior?.find(item => item.id === id);
      const currentSaved = prior ? !!previousEvent : saved;
      const nextSaved = desiredSaved ?? !currentSaved;
      const item = event ?? previousEvent ?? queryClient.getQueryData<EventOut>(['event', id]);
      if (item && prior) queryClient.setQueryData(['saved-events'], applySaved(prior, item, nextSaved));
      try {
        if (nextSaved) await eventsApi.saveEvent(id); else await eventsApi.unsaveEvent(id);
        if (!nextSaved && item) queryClient.setQueryData(['saved-undo'], item);
      } catch (error) {
        // Undo only this event: concurrent operations on other events survive.
        if (item && prior) queryClient.setQueryData<EventOut[]>(['saved-events'], (current: EventOut[] | undefined) => applySaved(current, item, currentSaved));
        throw error;
      }
    },
    onSettled: (_data, _error, variables) => {
      gate!.leave(variables.id);
      // The last outstanding mutation reconciles the shared library once.
      if (queryClient.isMutating({ mutationKey: ['save-event'] }) <= 1) {
        for (const queryKey of [['saved-events'], ['area-saved'], ['recommendations'], ['tonight'], ['event-chains']]) void queryClient.invalidateQueries({ queryKey });
      }
    },
  });
  return { ...mutation,
    mutate: (...args: Parameters<typeof mutation.mutate>) => { if (gate!.enter(args[0].id)) mutation.mutate(...args); },
    mutateAsync: (...args: Parameters<typeof mutation.mutateAsync>) => {
      if (!gate!.enter(args[0].id)) return Promise.resolve();
      return mutation.mutateAsync(...args);
    },
  };

}
