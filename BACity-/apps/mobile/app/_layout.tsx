import { useEffect, useState } from "react";
import { Stack } from "expo-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { useAuthStore } from "../src/store/authStore";
import { AppLoadingScreen } from "../src/components/AppLoadingScreen";
import { colors } from "../src/theme/colors";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1 } },
});

const MIN_BRAND_MS = 950;

export default function RootLayout() {
  const hydrate = useAuthStore((s) => s.hydrate);
  const authLoading = useAuthStore((s) => s.isLoading);
  const userId = useAuthStore((s) => s.user?.id);
  const [brandVisible, setBrandVisible] = useState(true);

  useEffect(() => {
    void hydrate();
    const timer = setTimeout(() => setBrandVisible(false), MIN_BRAND_MS);
    return () => clearTimeout(timer);
  }, [hydrate]);

  useEffect(() => {
    queryClient.clear();
  }, [userId]);

  return (
    <QueryClientProvider client={queryClient}>
      <SafeAreaProvider>
        <StatusBar style="dark" />
        {brandVisible || authLoading ? (
          <AppLoadingScreen />
        ) : (
          <Stack
            screenOptions={{
              headerShown: false,
              animation: "fade",
              contentStyle: { backgroundColor: colors.background },
            }}
          />
        )}
      </SafeAreaProvider>
    </QueryClientProvider>
  );
}
