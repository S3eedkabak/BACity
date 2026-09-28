import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { areaWatchesApi } from "../api/areaWatches";
import { accountQueryKey } from "../api/accountQueryKey";
import { useAuthStore } from "../store/authStore";

export function useAreaWatches(enabled: boolean) {
  const accountId = useAuthStore(state => state.user?.id ?? null);
  return useQuery({ queryKey: accountQueryKey("area-watches", accountId), queryFn: areaWatchesApi.list, enabled: enabled && !!accountId, staleTime: 30_000 });
}

export function useAreaWatch(id: string, enabled: boolean) {
  const accountId = useAuthStore(state => state.user?.id ?? null);
  return useQuery({ queryKey: accountQueryKey("area-watches", accountId, id), queryFn: () => areaWatchesApi.get(id), enabled: enabled && !!accountId && !!id });
}

export function useAreaWatchFeed(id: string, enabled: boolean) {
  const accountId = useAuthStore(state => state.user?.id ?? null);
  return useInfiniteQuery({
    queryKey: accountQueryKey("area-watches", accountId, id, "events"),
    queryFn: ({ pageParam }) => areaWatchesApi.events(id, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: page => page.next_cursor ?? undefined,
    enabled: enabled && !!accountId && !!id,
  });
}

export function useAreaWatchMutation(id?: string) {
  const client = useQueryClient();
  const accountId = useAuthStore(state => state.user?.id ?? null);
  return useMutation({
    mutationKey: accountQueryKey("area-watch-mutation", accountId, id),
    mutationFn: async (work: () => Promise<unknown>) => work(),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: accountQueryKey("area-watches", accountId) });
      if (id) await client.invalidateQueries({ queryKey: accountQueryKey("area-watches", accountId, id) });
    },
  });
}
