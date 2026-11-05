import { useThemeRevision } from '../src/theme/appearance';
import { useEffect } from "react";
import { router, useRootNavigationState } from "expo-router";
import { AppLoadingScreen } from "../src/components/AppLoadingScreen";
import { useAuthStore } from "../src/store/authStore";

export default function EntryScreen() {
  useThemeRevision();
  const token = useAuthStore((s) => s.token);
  const user = useAuthStore((s) => s.user);
  const loading = useAuthStore((s) => s.isLoading);
  const navigation = useRootNavigationState();

  useEffect(() => {
    if (loading || !navigation?.key) return;
    router.replace(token && user ? "/(tabs)/discover" : "/welcome");
  }, [token, user, loading, navigation?.key]);

  return <AppLoadingScreen />;
}
