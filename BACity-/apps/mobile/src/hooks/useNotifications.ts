import { AppState } from 'react-native';
import { useEffect, useState } from 'react';
import { useCallback } from 'react';
import { useFocusEffect } from 'expo-router';
import { useIsFocused } from '@react-navigation/native';
import { useQuery } from '@tanstack/react-query';
import { getNotificationSummary } from '../api/interactions';
import { useAuthStore } from '../store/authStore';
export function useNotificationSummary() {
  const [active, setActive] = useState(AppState.currentState === 'active');
  const token = useAuthStore(s => s.token); const focused = useIsFocused();
  const query = useQuery({ queryKey: ['notification-summary'], queryFn: getNotificationSummary, enabled: !!token, staleTime: 30000, refetchInterval: focused && active && !!token ? 30000 : false });
  useFocusEffect(useCallback(() => { if (token) void query.refetch(); }, [token, query.refetch]));
  useEffect(() => { const subscription = AppState.addEventListener('change', status => { setActive(status === 'active'); if (status === 'active' && token) void query.refetch(); }); return () => subscription.remove(); }, [token, query.refetch]);
  return query;
}
