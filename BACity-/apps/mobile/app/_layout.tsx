import { ActionFeedbackProvider } from "../src/components/interactions/ActionFeedback";
import { IconButton } from "../src/components/SocialUI";
import { ThemeScene } from "../src/components/navigation/ThemeScene";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { useMotionPreference } from "../src/components/interactions/useMotionPreference";
import { useAppearanceLifecycle } from "../src/theme/appearance";
import { getColorMode } from "../src/theme/colors";
import { useThemeRevision } from "../src/theme/appearance";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  router,
  Stack,
  usePathname,
  useRootNavigationState,
} from "expo-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { useAuthStore } from "../src/store/authStore";
import { colors } from "../src/theme/colors";
import { View } from "react-native";
import { StartupScene } from "../src/components/StartupScene";
import { LoadingExperienceProvider } from "../src/components/loading/LoadingExperience";
import { useReducedMotion } from "react-native-reanimated";
import { listEvents } from "../src/api/events";
import { entryDestination } from "../src/ux/motionPolicy";
import { sessionGreeting, type Greeting } from "../src/greeting/session";
import { SessionWelcome } from "../src/components/greeting/SessionWelcome";
import { DistrictMorphLayer } from "../src/map/DistrictMorphLayer";
import { useDistrictMorph } from "../src/map/districtMorphState";

export default function RootLayout() {
  useAppearanceLifecycle();
  useThemeRevision();
  const hydrate = useAuthStore((s) => s.hydrate);
  const authLoading = useAuthStore((s) => s.isLoading);
  const userId = useAuthStore((s) => s.user?.id);
  const entryKind = useAuthStore((s) => s.entryKind);
  const [greeting, setGreeting] = useState<Greeting | null>(null);
  const [completedOwner, setCompletedOwner] = useState<string | null>(null);
  const [finishedOwner, setFinishedOwner] = useState<string | null>(null);
  const navigatingOwner = useRef<string | null>(null);
  const entryOwner = useRef<string | undefined | null>(null);
  const pathname = usePathname();
  const navigation = useRootNavigationState();
  const reduced = useMotionPreference();
  const districtMorphActive = useDistrictMorph(
    (state) => state.phase !== "idle",
  );
  // Separate caches per session identity, without clearing queries after children mount.
  const queryClient = useMemo(
    () => new QueryClient({ defaultOptions: { queries: { retry: 1 } } }),
    [userId],
  );

  useEffect(() => {
    void hydrate();
  }, [hydrate]);

  useEffect(() => {
    if (entryOwner.current !== userId) {
      entryOwner.current = userId;
      setCompletedOwner(null);
      setFinishedOwner(null);
      navigatingOwner.current = null;
    }
    return () => queryClient.clear();
  }, [userId, queryClient]);

  const finishEntry = useCallback(() => {
    if (userId && useAuthStore.getState().user?.id === userId)
      setFinishedOwner(userId);
  }, [userId]);

  // Sign-in always resolves to Home, but never replays the cold-launch scene.
  useEffect(() => {
    if (userId) finishEntry();
  }, [userId, finishEntry]);

  useEffect(() => {
    if (!navigation?.key) return;
    setGreeting(
      sessionGreeting.claim(userId ?? null, authLoading, entryKind, Date.now()),
    );
  }, [userId, authLoading, entryKind, navigation?.key]);
  const completeGreeting = useCallback(() => {
    if (!greeting) return;
    sessionGreeting.finish(greeting.owner);
    setGreeting(null);
  }, [greeting]);

  useEffect(() => {
    if (!navigation?.key || completedOwner === userId) return;
    const destination = entryDestination(
      finishedOwner,
      userId ?? null,
      pathname,
    );
    if (destination === "home" && navigatingOwner.current !== userId) {
      navigatingOwner.current = userId ?? null;
      router.replace("/(tabs)/discover");
    }
    if (destination === "complete") setCompletedOwner(finishedOwner);
  }, [finishedOwner, userId, pathname, navigation?.key, completedOwner]);

  useEffect(() => {
    if (userId)
      void queryClient.prefetchQuery({
        queryKey: ["events", { limit: 24 }],
        queryFn: () => listEvents({ limit: 24 }),
        staleTime: 60_000,
      });
  }, [completedOwner, userId, queryClient]);

  const entryActive = !!userId && completedOwner !== userId;

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <View style={{ flex: 1, backgroundColor: colors.background }}>
          <ActionFeedbackProvider>
            <LoadingExperienceProvider>
              <StatusBar
                style={
                  districtMorphActive ||
                  pathname === "/map" ||
                  getColorMode() === "light"
                    ? "dark"
                    : "light"
                }
              />
              <ThemeScene>
                <QueryClientProvider
                  key={userId || "guest"}
                  client={queryClient}
                >
                  <Stack
                    screenOptions={{
                      headerShown: true,
                      headerStyle: { backgroundColor: colors.background },
                      headerTintColor: colors.text,
                      headerTitleStyle: { fontSize: 16, fontWeight: "600" },
                      headerBackTitleVisible: false,
                      headerBackVisible: false,
                      headerLeft: () => (
                        <IconButton
                          icon="chevron-back"
                          label="Go back"
                          onPress={() =>
                            router.canGoBack()
                              ? router.back()
                              : router.replace(
                                  userId ? "/(tabs)/discover" : "/welcome",
                                )
                          }
                        />
                      ),
                      headerShadowVisible: false,
                      gestureEnabled: true,
                      animationDuration: 160,
                      animation: reduced ? "none" : "fade",
                      contentStyle: { backgroundColor: colors.background },
                    }}
                  >
                    <Stack.Screen
                      name="(tabs)"
                      options={{ headerShown: false }}
                    />
                    <Stack.Screen
                      name="index"
                      options={{ headerShown: false }}
                    />
                    <Stack.Screen
                      name="welcome"
                      options={{ headerShown: false }}
                    />
                    <Stack.Screen name="auth" options={{ title: "Welcome", animation: reduced ? "none" : "slide_from_right", animationDuration: 300 }} />
                    <Stack.Screen
                      name="event/[id]"
                      options={{ title: "Event" }}
                    />
                    <Stack.Screen
                      name="account"
                      options={{ title: "Account" }}
                    />
                    <Stack.Screen
                      name="area-events"
                      options={({ route }) => ({
                        headerShown: !(
                          route.params as { districtMorph?: string } | undefined
                        )?.districtMorph,
                        animation: districtMorphActive
                          ? "none"
                          : reduced
                            ? "none"
                            : "fade",
                        gestureEnabled: !districtMorphActive,
                      })}
                    />
                  </Stack>
                  <DistrictMorphLayer />
                </QueryClientProvider>
              </ThemeScene>
              <StartupScene
                ready={!authLoading && !!navigation?.key && !entryActive}
                onRetry={() => void hydrate()}
              />
            </LoadingExperienceProvider>
          </ActionFeedbackProvider>
          {greeting && greeting.owner === userId && (
            <SessionWelcome greeting={greeting} onComplete={completeGreeting} />
          )}
        </View>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
