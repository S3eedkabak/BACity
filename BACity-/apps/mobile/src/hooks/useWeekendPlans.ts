import { useMutation } from "@tanstack/react-query";
import { generateWeekendPlans, WeekendPlanRequest } from "../api/weekendPlans";
import { accountQueryKey } from "../api/accountQueryKey";
import { useAuthStore } from "../store/authStore";

export function useWeekendPlans() {
  const accountId = useAuthStore(state => state.user?.id ?? null);
  return useMutation({ mutationKey: accountQueryKey("weekend-plan", accountId), mutationFn: (payload: WeekendPlanRequest) => generateWeekendPlans(payload) });
}
