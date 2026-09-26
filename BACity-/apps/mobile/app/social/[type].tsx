import { useCallback, useEffect, useState } from "react";
import { FlatList, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router, useLocalSearchParams } from "expo-router";
import { follow, getFollows, getProfileHistory, unfollow, type FollowRecord } from "../../src/api/community";
import { ListItem, ProfileRow, ScreenHeader, SkeletonList } from "../../src/components/SocialUI";
import { EmptyState } from "../../src/components/EmptyState";
import { useAuthStore } from "../../src/store/authStore";
import { colors } from "../../src/theme/colors";

const PAGE = 20;
export default function SocialListScreen() {
  const { type, userId } = useLocalSearchParams<{ type: "followers" | "following"; userId?: string }>();
  const me = useAuthStore(state => state.user); const targetId = userId || me?.id || "";
  const [items, setItems] = useState<any[]>([]); const [mine, setMine] = useState<FollowRecord[]>([]); const [loading, setLoading] = useState(true); const [more, setMore] = useState(false); const [error, setError] = useState(""); const [busy, setBusy] = useState("");
  const load = useCallback(async (append = false) => { if (!targetId || !type) return; setLoading(true); setError(""); try { const [page, follows] = await Promise.all([getProfileHistory(targetId, type, append ? items.length : 0, PAGE), getFollows(0, 100)]); setItems(current => append ? [...current, ...page] : page); setMine(follows); setMore(page.length === PAGE); } catch (e: any) { setError(e.message); } finally { setLoading(false); } }, [items.length, targetId, type]);
  useEffect(() => { setItems([]); if (me) void load(false); else setLoading(false); }, [targetId, type, me?.id]);
  async function toggle(profile: any) { const existing = mine.find(item => ["user", "guide"].includes(item.target_type) && item.target_id === profile.id); setBusy(profile.id); try { if (existing) await unfollow(existing.id); else await follow(profile.role === "GUIDE" ? "guide" : "user", profile.id); await load(false); } catch (e: any) { setError(e.message); } finally { setBusy(""); } }
  const title = type === "followers" ? "Followers" : "Following";
  return <SafeAreaView style={styles.safe} edges={["top", "bottom"]}><ScreenHeader title={title} />
    {!me ? <EmptyState title="Sign in to view social connections" action="Sign in" onAction={() => router.push({ pathname: "/auth", params: { mode: "login" } })} /> : <>
    {error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}
    {loading && !items.length ? <View style={styles.content}><SkeletonList /></View> : <FlatList data={items} keyExtractor={item => item.id} contentContainerStyle={styles.content} ListEmptyComponent={<EmptyState title={`No ${title.toLowerCase()} yet`} subtitle={type === "followers" ? "People who follow this profile will appear here." : "Followed people and local interests will appear here."} action={type === "following" && targetId === me?.id ? "Find people and interests" : undefined} onAction={type === "following" && targetId === me?.id ? () => router.push("/following") : undefined} />} renderItem={({ item }) => {
      const profile = type === "followers" ? item : ["user", "guide"].includes(item.target_type) ? { id: item.target_id, display_name: item.target_label, neighborhood: item.target_subtitle, role: item.target_type === "guide" ? "GUIDE" : "USER" } : null;
      if (!profile) return <ListItem icon={item.target_type === "organizer" ? "business-outline" : item.target_type === "venue" ? "location-outline" : "pricetag-outline"} title={item.target_label} subtitle={`${item.target_type} · ${item.target_subtitle}`} />;
      const existing = mine.some(link => ["user", "guide"].includes(link.target_type) && link.target_id === profile.id);
      return <ProfileRow profile={profile} subtitle={profile.reputation_level || profile.neighborhood || item.target_subtitle} onPress={() => router.push(`/member/${profile.id}`)} action={profile.id === me?.id ? undefined : busy === profile.id ? "…" : existing ? "Following" : "Follow"} onAction={profile.id === me?.id ? undefined : () => toggle(profile)} />;
    }} ListFooterComponent={more ? <Text style={styles.more} onPress={() => load(true)}>{loading ? "Loading…" : "Load more"}</Text> : null} />}
    </>}
  </SafeAreaView>;
}
const styles = StyleSheet.create({ safe: { flex: 1, backgroundColor: colors.background }, content: { paddingHorizontal: 18, paddingBottom: 28, flexGrow: 1 }, error: { marginHorizontal: 18, padding: 12, color: colors.danger, backgroundColor: colors.surface }, more: { color: colors.primaryDark, textAlign: "center", padding: 18 } });
