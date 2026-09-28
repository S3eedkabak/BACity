import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getEntitlements } from "../api/entitlements";
import { useAuthStore } from "../store/authStore";

export const ENTITLEMENTS_QUERY_KEY = ["entitlements"] as const;

export function useEntitlements() {
  const authenticated = useAuthStore(state => !!state.token);
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ENTITLEMENTS_QUERY_KEY,
    queryFn: getEntitlements,
    enabled: authenticated,
    staleTime: 60_000,
  });

  return {
    ...query,
    authenticated,
    plus: query.data?.bacity_plus ?? null,
    refresh: () => queryClient.invalidateQueries({ queryKey: ENTITLEMENTS_QUERY_KEY }),
  };
}
