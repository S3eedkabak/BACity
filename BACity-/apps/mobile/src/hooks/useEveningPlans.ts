import { useMutation } from "@tanstack/react-query";
import { EveningPlanRequest, generateEveningPlans } from "../api/eveningPlans";
import { accountQueryKey } from "../api/accountQueryKey";
import { useAuthStore } from "../store/authStore";

export function useEveningPlans() {
  const accountId = useAuthStore(state => state.user?.id ?? null);
  return useMutation({ mutationKey: accountQueryKey("evening-plan", accountId), mutationFn: (payload: EveningPlanRequest) => generateEveningPlans(payload) });
}
