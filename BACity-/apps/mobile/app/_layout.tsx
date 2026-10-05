import { useEffect, useMemo, useState } from "react";
import { Stack } from "expo-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { useAuthStore } from "../src/store/authStore";
import { AppLoadingScreen } from "../src/components/AppLoadingScreen";
import { colors } from "../src/theme/colors";
import { View, StyleSheet } from 'react-native';
import { BACityEntrySequence, BACityLoadingProvider } from '../src/components/BACityMotion';
import { listEvents } from '../src/api/events';

export default function RootLayout() {
  const hydrate = useAuthStore((s) => s.hydrate);
  const authLoading = useAuthStore((s) => s.isLoading);
  const userId = useAuthStore((s) => s.user?.id);
  const [completedOwner, setCompletedOwner] = useState<string | null>(null);
  // Separate caches per session identity, without clearing queries after children mount.
  const queryClient = useMemo(() => new QueryClient({ defaultOptions: { queries: { retry: 1 } } }), [userId]);

  useEffect(() => {
    void hydrate();
  }, [hydrate]);

  useEffect(() => {
    setCompletedOwner(null);
    if (userId) void queryClient.prefetchQuery({ queryKey: ['events', { limit: 24 }], queryFn: () => listEvents({ limit: 24 }), staleTime: 60_000 });
    return () => queryClient.clear();
  }, [userId, queryClient]);

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
        {entryActive ? <BACityEntrySequence key={userId} onComplete={() => setCompletedOwner(userId)} /> : null}
        </BACityLoadingProvider>
      </SafeAreaProvider>
    </QueryClientProvider>
  );
}
