import { useEffect } from "react";
import { router, useLocalSearchParams } from "expo-router";
import { LoadingState } from "../src/components/LoadingState";

const DESTINATIONS: Record<string, string> = {
  recommendations: "/(tabs)/discover", promotions: "/(tabs)/discover", messages: "/messages",
  notifications: "/notifications", people: "/(tabs)/explore?domain=people", places: "/(tabs)/explore?domain=places",
  organizations: "/(tabs)/explore?domain=organizers", collections: "/collections", follows: "/following",
  utilities: "/utilities", submissions: "/activity", moderation: "/moderator", reports: "/moderator",
  audit: "/moderator", blocks: "/blocked",
};

/** Compatibility route for old links. Community capabilities now live in focused screens. */
export default function CommunityRedirect() {
  const { section } = useLocalSearchParams<{ section?: string }>();
  useEffect(() => { router.replace((DESTINATIONS[section || ""] || "/(tabs)/discover") as any); }, [section]);
  return <LoadingState />;
}
