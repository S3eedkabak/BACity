import { useEffect } from "react";
import { router } from "expo-router";
import { AppLoadingScreen } from "../src/components/AppLoadingScreen";
import { useAuthStore } from "../src/store/authStore";

export default function EntryScreen() {
  const token = useAuthStore((s) => s.token);
  const user = useAuthStore((s) => s.user);

  useEffect(() => {
    const timer = setTimeout(() => {
      router.replace(token && user ? "/(tabs)" : "/welcome");
    }, 120);
    return () => clearTimeout(timer);
  }, [token, user]);

  return <AppLoadingScreen />;
}
