import { useQuery } from "@tanstack/react-query";
import { getTonightRecommendations } from "../api/tonight";
import { RecommendationCoordinates } from "../recommendations/useRecommendationLocation";
import { accountQueryKey } from "../api/accountQueryKey";
import { useAuthStore } from "../store/authStore";

export function useTonight(enabled: boolean, coordinates: RecommendationCoordinates | null) {
  const accountId = useAuthStore(state => state.user?.id ?? null);
  return useQuery({
    queryKey: accountQueryKey("tonight", accountId, coordinates?.latitude ?? null, coordinates?.longitude ?? null),
    queryFn: () => getTonightRecommendations(coordinates),
    enabled: enabled && !!accountId,
    staleTime: 60_000,
  });
}
