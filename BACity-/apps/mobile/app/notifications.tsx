import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getNotifications, markNotificationRead, type Notification } from "../src/api/community";
import { ScreenHeader, SkeletonList } from "../src/components/SocialUI";
import { EmptyState } from "../src/components/EmptyState";
import { useAuthStore } from "../src/store/authStore";
import { colors } from "../src/theme/colors";
import { fonts } from "../src/theme/fonts";

function icon(kind: string): keyof typeof Ionicons.glyphMap {
  if (kind === "message") return "chatbubble-outline";
  if (kind === "moderation") return "checkmark-circle-outline";
  if (kind === "organizer") return "business-outline";
  return "notifications-outline";
}

export default function NotificationsScreen() {
  const token = useAuthStore(state => state.token); const client = useQueryClient();
  const query = useQuery({ queryKey: ["notifications"], queryFn: getNotifications, enabled: !!token });
  async function open(item: Notification) {
    if (!item.read_at) { await markNotificationRead(item.id); client.setQueryData<Notification[]>(["notifications"], (current: Notification[] | undefined) => current?.map((value: Notification) => value.id === item.id ? { ...value, read_at: new Date().toISOString() } : value)); }
    if (item.kind === "message" && item.target_id) router.push(`/messages/${item.target_id}`);
    else if (item.kind === "moderation") router.push("/activity");
    else if (item.kind === "organizer") router.push({ pathname: "/(tabs)/explore", params: { domain: "organizers" } });
  }
  return <SafeAreaView style={styles.safe} edges={["top", "bottom"]}><ScreenHeader title="Activity" />
    {!token ? <EmptyState title="Sign in to see activity" subtitle="Updates about messages, contributions and organizers appear here." action="Sign in" onAction={() => router.push({ pathname: "/auth", params: { mode: "login" } })} /> : query.isPending ? <View style={styles.content}><SkeletonList /></View> : query.isError ? <EmptyState title="Activity couldn't load" subtitle={query.error.message} action="Try again" onAction={() => query.refetch()} /> : <FlatList data={query.data} keyExtractor={item => item.id} contentContainerStyle={styles.content} refreshing={query.isRefetching} onRefresh={query.refetch} ListEmptyComponent={<EmptyState title="You're all caught up" subtitle="New community activity will appear here." />} renderItem={({ item }) => <Pressable onPress={() => open(item)} style={({ pressed }) => [styles.row, !item.read_at && styles.unreadRow, pressed && styles.pressed]}>
      <View style={styles.icon}><Ionicons name={icon(item.kind)} size={21} color={colors.primaryDark} /></View><View style={styles.copy}><Text style={[styles.body, !item.read_at && styles.bodyUnread]}>{item.body}</Text><Text style={styles.time}>{new Date(item.created_at).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</Text></View>{!item.read_at && <View style={styles.dot} />}
    </Pressable>} />}
  </SafeAreaView>;
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background }, content: { paddingHorizontal: 18, paddingBottom: 28, flexGrow: 1 },
  row: { minHeight: 76, paddingVertical: 11, flexDirection: "row", alignItems: "center", gap: 12, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border }, unreadRow: { backgroundColor: colors.primarySoft }, pressed: { opacity: .72 },
  icon: { width: 46, height: 46, borderRadius: 17, backgroundColor: colors.surface, alignItems: "center", justifyContent: "center" }, copy: { flex: 1 }, body: { color: colors.text, fontFamily: fonts.regular, fontSize: 13, lineHeight: 18 }, bodyUnread: { fontFamily: fonts.semibold }, time: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 9, marginTop: 4 }, dot: { width: 9, height: 9, borderRadius: 5, backgroundColor: colors.primary, marginRight: 5 },
});
