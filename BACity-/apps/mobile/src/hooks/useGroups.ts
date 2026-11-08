import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { groupsApi } from "../api/groups";
import { accountQueryKey } from "../api/accountQueryKey";
import { useAuthStore } from "../store/authStore";

export function useGroups(enabled: boolean) {
  const accountId = useAuthStore(state => state.user?.id ?? null);
  return useQuery({ queryKey: accountQueryKey("groups", accountId), queryFn: groupsApi.list, enabled: enabled && !!accountId, staleTime: 15_000 });
}

export function useGroup(id: string, enabled: boolean) {
  const accountId = useAuthStore(state => state.user?.id ?? null);
  return useQuery({
    queryKey: accountQueryKey("groups", accountId, id), queryFn: () => groupsApi.get(id), enabled: enabled && !!accountId && !!id,
    refetchInterval: query => ["open", "ready", "voting"].includes(query.state.data?.status ?? "") ? 5_000 : false,
  });
}

export function useGroupMutation(id?: string) {
  const client = useQueryClient();
  const accountId = useAuthStore(state => state.user?.id ?? null);
  return useMutation({
    mutationKey: accountQueryKey("groups-mutation", accountId, id),
    mutationFn: async (work: () => Promise<unknown>) => work(),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: accountQueryKey("groups", accountId) });
      if (id) await client.invalidateQueries({ queryKey: accountQueryKey("groups", accountId, id) });
    },
  });
}
