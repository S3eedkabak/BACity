import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { areaWatchesApi } from "../api/areaWatches";

export function useAreaWatches(enabled: boolean) {
  return useQuery({ queryKey: ["area-watches"], queryFn: areaWatchesApi.list, enabled, staleTime: 30_000 });
}

export function useAreaWatch(id: string, enabled: boolean) {
  return useQuery({ queryKey: ["area-watches", id], queryFn: () => areaWatchesApi.get(id), enabled: enabled && !!id });
}

export function useAreaWatchFeed(id: string, enabled: boolean) {
  return useInfiniteQuery({
    queryKey: ["area-watches", id, "events"],
    queryFn: ({ pageParam }) => areaWatchesApi.events(id, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: page => page.next_cursor ?? undefined,
    enabled: enabled && !!id,
  });
}

export function useAreaWatchMutation(id?: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (work: () => Promise<unknown>) => work(),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["area-watches"] });
      if (id) await client.invalidateQueries({ queryKey: ["area-watches", id] });
    },
  });
}
