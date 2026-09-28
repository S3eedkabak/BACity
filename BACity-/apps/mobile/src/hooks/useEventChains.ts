import { useQuery } from "@tanstack/react-query";
import { EventChainMode, getEventChains } from "../api/eventChains";
import { accountQueryKey } from "../api/accountQueryKey";
import { useAuthStore } from "../store/authStore";

export function useEventChains(anchorEventId: string | undefined, mode: EventChainMode, enabled: boolean) {
  const accountId = useAuthStore(state => state.user?.id ?? null);
  return useQuery({
    queryKey: accountQueryKey("event-chains", accountId, anchorEventId, mode),
    queryFn: () => getEventChains(anchorEventId as string, mode),
    enabled: enabled && !!accountId && !!anchorEventId,
    staleTime: 60_000,
  });
}
