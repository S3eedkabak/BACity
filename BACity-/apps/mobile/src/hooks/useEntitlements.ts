import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getEntitlements } from "../api/entitlements";
import { accountQueryKey } from "../api/accountQueryKey";
import { useAuthStore } from "../store/authStore";

export function useEntitlements() {
  const token = useAuthStore(state => state.token);
  const accountId = useAuthStore(state => state.user?.id ?? null);
  const authenticated = !!token && !!accountId;
  const queryClient = useQueryClient();
  const queryKey = accountQueryKey("entitlements", accountId);
  const query = useQuery({
    queryKey,
    queryFn: getEntitlements,
    enabled: authenticated,
    staleTime: 15_000,
    refetchInterval: authenticated ? 60_000 : false,
  });

  return {
    ...query,
    authenticated,
    plus: query.data?.bacity_plus ?? null,
    refresh: () => queryClient.invalidateQueries({ queryKey }),
  };
}
