import { useMutation } from "@tanstack/react-query";
import { generateWeekendPlans, WeekendPlanRequest } from "../api/weekendPlans";

export function useWeekendPlans() {
  return useMutation({ mutationFn: (payload: WeekendPlanRequest) => generateWeekendPlans(payload) });
}
