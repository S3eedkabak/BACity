import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { groupsApi } from "../api/groups";

export function useGroups(enabled: boolean) {
  return useQuery({ queryKey: ["groups"], queryFn: groupsApi.list, enabled, staleTime: 15_000 });
}

export function useGroup(id: string, enabled: boolean) {
  return useQuery({
    queryKey: ["groups", id], queryFn: () => groupsApi.get(id), enabled: enabled && !!id,
    refetchInterval: query => ["open", "ready", "voting"].includes(query.state.data?.status ?? "") ? 5_000 : false,
  });
}

export function useGroupMutation(id?: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (work: () => Promise<unknown>) => work(),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["groups"] });
      if (id) await client.invalidateQueries({ queryKey: ["groups", id] });
    },
  });
}
