import { useInfiniteQuery } from "@tanstack/react-query";
import { getRecommendations } from "../api/recommendations";
import { RecommendationCoordinates } from "../recommendations/useRecommendationLocation";

const PAGE_SIZE = 10;

export function useRecommendations(enabled: boolean, coordinates: RecommendationCoordinates | null) {
  return useInfiniteQuery({
    queryKey: ["recommendations", coordinates?.latitude ?? null, coordinates?.longitude ?? null],
    queryFn: ({ pageParam }) => getRecommendations({
      offset: pageParam,
      limit: PAGE_SIZE,
      latitude: coordinates?.latitude,
      longitude: coordinates?.longitude,
    }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, pages) => lastPage.length === PAGE_SIZE
      ? pages.reduce((total, page) => total + page.length, 0)
      : undefined,
    enabled,
    staleTime: 60_000,
  });
}
