import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { follow, unfollow, type FollowRecord } from '../api/community';
import { apiRequest } from '../api/client';
import { useAuthStore } from '../store/authStore';
import { createActionGate } from '../interactions/policy';
const gates = new WeakMap<object, ReturnType<typeof createActionGate>>();
/** Entity-specific query avoids truncating following state to the first 50 follows. */
export function useFollowAction(type: string, id: string) {
  const client = useQueryClient(); const token = useAuthStore(s => s.token);
  const key = ['follow-state', type, id];
  const state = useQuery({ queryKey: key, queryFn: () => apiRequest<{ id: string | null; following: boolean }>('/community/follow-state', { auth: true, params: { target_type: type, target_id: id } }), enabled: !!token, staleTime: 30000 });
  let gate = gates.get(client); if (!gate) { gate = createActionGate(); gates.set(client, gate); }
  const mutation = useMutation({
    mutationKey: ['follow-action', type, id],
    mutationFn: async () => {
      const prior = client.getQueryData<{ id: string | null; following: boolean }>(key);
      if (!prior) throw new Error('Follow status is unavailable. Try again.');
      await client.cancelQueries({ queryKey: key });
      client.setQueryData(key, { ...prior, following: !prior.following });
      try {
        if (prior.following && prior.id) { await unfollow(prior.id); client.setQueryData(key, { id: null, following: false }); }
        else { const value = await follow(type, id) as FollowRecord; client.setQueryData(key, { id: value.id, following: true }); }
      } catch (error) { client.setQueryData(key, prior); throw error; }
    },
    onSettled: () => {
      gate!.leave(`${type}:${id}`);
      if (client.isMutating({ mutationKey: ['follow-action', type, id] }) > 1) return;
      for (const queryKey of [key, ['follows'], ['profile'], ['recommendations'], ['social-history']]) void client.invalidateQueries({ queryKey });
    },
  });
  return { state, mutation, signedIn: !!token, toggle: () => { if (gate!.enter(`${type}:${id}`)) mutation.mutate(); } };
}
