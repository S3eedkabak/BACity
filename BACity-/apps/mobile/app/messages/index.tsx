import { useMemo } from "react";
import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { useQueries, useQuery } from "@tanstack/react-query";
import { useAuthStore } from "../../src/store/authStore";
import { getConversation, getNotifications, getProfile } from "../../src/api/community";
import { Avatar, ScreenHeader, SkeletonList } from "../../src/components/SocialUI";
import { EmptyState } from "../../src/components/EmptyState";
import { colors } from "../../src/theme/colors";
import { fonts } from "../../src/theme/fonts";

function when(value?: string) {
  if (!value) return "";
  const date = new Date(value);
  return date.toLocaleDateString(undefined, date.toDateString() === new Date().toDateString() ? { hour: "2-digit", minute: "2-digit" } : { day: "numeric", month: "short" });
}

export default function InboxScreen() {
  const token = useAuthStore(state => state.token);
  const notifications = useQuery({ queryKey: ["notifications"], queryFn: getNotifications, enabled: !!token });
  const userIds = useMemo(() => Array.from(new Set((notifications.data ?? []).filter(item => item.kind === "message" && item.target_id).map(item => item.target_id!))), [notifications.data]);
  const conversations = useQueries({ queries: userIds.map(userId => ({
    queryKey: ["inbox-thread", userId],
    queryFn: async () => ({ userId, profile: await getProfile(userId), messages: await getConversation(userId) }),
  })) });
  const rows = conversations.map(result => result.data).filter(Boolean).map(thread => ({
    ...thread!, latest: thread!.messages[0],
    unread: (notifications.data ?? []).some(item => item.kind === "message" && item.target_id === thread!.userId && !item.read_at),
  })).sort((a, b) => new Date(b.latest?.created_at ?? 0).getTime() - new Date(a.latest?.created_at ?? 0).getTime());
  const loading = notifications.isPending || conversations.some(result => result.isPending);
  const error = notifications.error || conversations.find(result => result.error)?.error;

  return <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
    <ScreenHeader title="Messages" />
    {!token ? <EmptyState title="Sign in to message people" subtitle="Conversations are available to signed-in BACity members." action="Sign in" onAction={() => router.push({ pathname: "/auth", params: { mode: "login" } })} /> : loading ? <View style={styles.content}><SkeletonList /></View> : error ? <EmptyState title="Messages couldn't load" subtitle={(error as Error).message} action="Try again" onAction={() => notifications.refetch()} /> : (
      <FlatList
        data={rows}
        keyExtractor={item => item.userId}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
        ListEmptyComponent={<EmptyState title="No conversations yet" subtitle="Open a member profile and tap Message to start one." action="Find people" onAction={() => router.push({ pathname: "/(tabs)/explore", params: { domain: "people" } })} />}
        renderItem={({ item }) => <Pressable onPress={() => router.push(`/messages/${item.userId}`)} style={({ pressed }) => [styles.row, pressed && styles.pressed]}>
          <Avatar uri={item.profile.avatar_url} name={item.profile.display_name} size={54} />
          <View style={styles.copy}><View style={styles.titleRow}><Text style={[styles.name, item.unread && styles.unread]} numberOfLines={1}>{item.profile.display_name || "BACity member"}</Text><Text style={styles.time}>{when(item.latest?.created_at)}</Text></View><Text style={[styles.preview, item.unread && styles.previewUnread]} numberOfLines={1}>{item.latest?.body || "New message"}</Text></View>
          {item.unread && <View style={styles.dot} />}
        </Pressable>}
      />
    )}
  </SafeAreaView>;
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  content: { paddingHorizontal: 18, paddingBottom: 24, flexGrow: 1 },
  row: { minHeight: 78, flexDirection: "row", alignItems: "center", gap: 12, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  pressed: { backgroundColor: colors.surfaceAlt },
  copy: { flex: 1, minWidth: 0 }, titleRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 },
  name: { flex: 1, color: colors.text, fontFamily: fonts.semibold, fontSize: 14 }, unread: { fontFamily: fonts.black },
  preview: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 11, marginTop: 4 }, previewUnread: { color: colors.text, fontFamily: fonts.medium },
  time: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 9 }, dot: { width: 9, height: 9, borderRadius: 5, backgroundColor: colors.primary },
});
