import { useQuery } from "@tanstack/react-query";
import { EventChainMode, getEventChains } from "../api/eventChains";

export function useEventChains(anchorEventId: string | undefined, mode: EventChainMode, enabled: boolean) {
  return useQuery({
    queryKey: ["event-chains", anchorEventId, mode],
    queryFn: () => getEventChains(anchorEventId as string, mode),
    enabled: enabled && !!anchorEventId,
    staleTime: 60_000,
  });
}
