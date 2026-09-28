import { useMutation } from "@tanstack/react-query";
import { EveningPlanRequest, generateEveningPlans } from "../api/eveningPlans";

export function useEveningPlans() {
  return useMutation({ mutationFn: (payload: EveningPlanRequest) => generateEveningPlans(payload) });
}
