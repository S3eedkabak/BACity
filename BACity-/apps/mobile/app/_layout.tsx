import { useCallback, useEffect, useMemo, useState } from "react";
import { router, Stack, usePathname, useRootNavigationState } from "expo-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { useAuthStore } from "../src/store/authStore";
import { AppLoadingScreen } from "../src/components/AppLoadingScreen";
import { colors } from "../src/theme/colors";
import { View, StyleSheet } from 'react-native';
import { BACityEntrySequence, BACityLoadingProvider, prepareEntryFilm } from '../src/components/BACityMotion';
import { listEvents } from '../src/api/events';
import { entryDestination } from '../src/ux/motionPolicy';

export default function RootLayout() {
  const hydrate = useAuthStore((s) => s.hydrate);
  const authLoading = useAuthStore((s) => s.isLoading);
  const userId = useAuthStore((s) => s.user?.id);
  const [completedOwner, setCompletedOwner] = useState<string | null>(null);
  const [finishedOwner, setFinishedOwner] = useState<string | null>(null);
  const pathname = usePathname();
  const navigation = useRootNavigationState();
  // Separate caches per session identity, without clearing queries after children mount.
  const queryClient = useMemo(() => new QueryClient({ defaultOptions: { queries: { retry: 1 } } }), [userId]);

  useEffect(() => {
    void hydrate();
    // Warm the bundled clip before the user completes sign-in; never stream it at entry.
    void prepareEntryFilm().catch(() => {});
  }, [hydrate]);

  useEffect(() => {
    setCompletedOwner(null);
    setFinishedOwner(null);
    return () => queryClient.clear();
  }, [userId, queryClient]);

  const finishEntry = useCallback(() => {
    if (userId && useAuthStore.getState().user?.id === userId) setFinishedOwner(userId);
  }, [userId]);

  useEffect(() => {
    if (!navigation?.key || completedOwner === userId) return;
    const destination = entryDestination(finishedOwner, userId ?? null, pathname);
    if (destination === 'home') router.replace('/(tabs)/discover');
    if (destination === 'complete') setCompletedOwner(finishedOwner);
  }, [finishedOwner, userId, pathname, navigation?.key, completedOwner]);

  useEffect(() => {
    if (userId && completedOwner === userId) void queryClient.prefetchQuery({ queryKey: ['events', { limit: 24 }], queryFn: () => listEvents({ limit: 24 }), staleTime: 60_000 });
  }, [completedOwner, userId, queryClient]);

  const entryActive = !!userId && completedOwner !== userId;

  return (
    <QueryClientProvider key={userId || 'guest'} client={queryClient}>
      <SafeAreaProvider>
        <StatusBar style="dark" />
        <BACityLoadingProvider entryActive={entryActive}>
          <Stack
            screenOptions={{
              headerShown: false,
              animation: "slide_from_right",
              contentStyle: { backgroundColor: colors.background },
            }}
          />
        {authLoading && !userId ? <View style={StyleSheet.absoluteFill}><AppLoadingScreen /></View> : null}
        {entryActive ? <BACityEntrySequence key={userId} onComplete={finishEntry} /> : null}
        </BACityLoadingProvider>
      </SafeAreaProvider>
    </QueryClientProvider>
  );
}
