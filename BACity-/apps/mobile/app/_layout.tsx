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

const MIN_BOOT_MS = 1400;

export default function RootLayout() {
  const hydrate = useAuthStore((s) => s.hydrate);
  const authLoading = useAuthStore((s) => s.isLoading);
  const [bootVisible, setBootVisible] = useState(true);

  useEffect(() => {
    hydrate();
    const timer = setTimeout(() => setBootVisible(false), MIN_BOOT_MS);

    return () => clearTimeout(timer);
  }, [hydrate]);

  return (
    <QueryClientProvider client={queryClient}>
      <SafeAreaProvider>
        <StatusBar style="dark" />
        {bootVisible || authLoading ? (
          <AppLoadingScreen />
        ) : (
          <Stack
            screenOptions={{
              headerStyle: { backgroundColor: colors.background },
              headerTintColor: colors.text,
              headerTitleStyle: {
                fontFamily: "System",
                fontWeight: "600",
              },
              contentStyle: { backgroundColor: colors.background },
            }}
          >
            <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
            <Stack.Screen name="event/[id]" options={{ title: "Event" }} />
          </Stack>
        )}
      </SafeAreaProvider>
    </QueryClientProvider>
  );
}
