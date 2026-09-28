import { useQuery } from "@tanstack/react-query";
import { getTonightRecommendations } from "../api/tonight";
import { RecommendationCoordinates } from "../recommendations/useRecommendationLocation";

export function useTonight(enabled: boolean, coordinates: RecommendationCoordinates | null) {
  return useQuery({
    queryKey: ["tonight", coordinates?.latitude ?? null, coordinates?.longitude ?? null],
    queryFn: () => getTonightRecommendations(coordinates),
    enabled,
    staleTime: 60_000,
  });
}
