import { useEffect, useState } from "react";
import { FlatList, KeyboardAvoidingView, Platform, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams, router } from "expo-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "../../src/api/client";
import { getConversation, getNotifications, getProfile, markNotificationRead, sendMessage } from "../../src/api/community";
import { Avatar, IconButton, ListItem, OverflowMenu, ScreenHeader, SkeletonList } from "../../src/components/SocialUI";
import { EmptyState } from "../../src/components/EmptyState";
import { Notice } from "../../src/components/CommunityUI";
import { useAuthStore } from "../../src/store/authStore";
import { colors } from "../../src/theme/colors";
import { fonts } from "../../src/theme/fonts";

export default function ConversationScreen() {
  const { userId } = useLocalSearchParams<{ userId: string }>();
  const me = useAuthStore(state => state.user);
  const queryClient = useQueryClient();
  const [body, setBody] = useState(""); const [notice, setNotice] = useState(""); const [menu, setMenu] = useState(false); const [reason, setReason] = useState("");
  const profile = useQuery({ queryKey: ["profile", userId], queryFn: () => getProfile(userId), enabled: !!userId });
  const thread = useQuery({ queryKey: ["conversation", userId], queryFn: () => getConversation(userId), enabled: !!userId });
  const notifications = useQuery({ queryKey: ["notifications"], queryFn: getNotifications });
  useEffect(() => {
    const unread = (notifications.data ?? []).filter(item => item.kind === "message" && item.target_id === userId && !item.read_at);
    if (!unread.length) return;
    void Promise.all(unread.map(item => markNotificationRead(item.id))).then(() => queryClient.invalidateQueries({ queryKey: ["notifications"] }));
  }, [notifications.data, queryClient, userId]);
  const send = useMutation({ mutationFn: () => sendMessage(userId, body.trim()), onSuccess: async () => { setBody(""); await thread.refetch(); queryClient.invalidateQueries({ queryKey: ["inbox-thread", userId] }); }, onError: (error: Error) => setNotice(error.message) });
  async function safety(path: string, payload?: unknown) { try { await apiRequest(path, { method: "POST", auth: true, body: payload }); setMenu(false); setNotice("Saved."); } catch (error: any) { setNotice(error.message); } }
  const messages = [...(thread.data ?? [])].reverse();

  return <SafeAreaView style={styles.safe} edges={["top", "bottom"]}><KeyboardAvoidingView style={styles.safe} behavior={Platform.OS === "ios" ? "padding" : undefined}>
    <ScreenHeader title={profile.data?.display_name || "Conversation"} right={<IconButton icon="ellipsis-horizontal" label="Conversation options" onPress={() => setMenu(true)} />} />
    <Notice text={notice} />
    {thread.isPending || profile.isPending ? <View style={styles.loading}><SkeletonList rows={4} /></View> : thread.isError ? <EmptyState title="Conversation unavailable" subtitle={thread.error.message} action="Try again" onAction={() => thread.refetch()} /> : <FlatList
      data={messages} keyExtractor={item => item.id} contentContainerStyle={styles.messages} keyboardShouldPersistTaps="handled"
      ListEmptyComponent={<EmptyState title="Start the conversation" subtitle="Say hello and keep it local." />}
      renderItem={({ item }) => { const mine = item.sender_id === me?.id; return <View style={[styles.messageRow, mine && styles.messageRowMine]}>{!mine && <Avatar uri={profile.data?.avatar_url} name={profile.data?.display_name} size={30} />}<View style={[styles.bubble, mine ? styles.bubbleMine : styles.bubbleTheirs]}><Text style={[styles.message, mine && styles.messageMine]}>{item.body}</Text><Text style={[styles.messageTime, mine && styles.messageTimeMine]}>{new Date(item.created_at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}</Text></View></View>; }}
    />}
    <View style={styles.composer}><TextInput accessibilityLabel="Message" placeholder="Message…" placeholderTextColor={colors.textMuted} value={body} onChangeText={setBody} multiline style={styles.input} /><Pressable accessibilityRole="button" accessibilityLabel="Send message" disabled={!body.trim() || send.isPending} onPress={() => send.mutate()} style={({ pressed }) => [styles.send, pressed && styles.pressed, (!body.trim() || send.isPending) && styles.disabled]}><Ionicons name="arrow-up" size={20} color={colors.white} /></Pressable></View>
    <OverflowMenu visible={menu} title="Conversation options" onClose={() => setMenu(false)}>
      <ListItem icon="person-outline" title="View profile" onPress={() => { setMenu(false); router.push(`/member/${userId}`); }} />
      <TextInput accessibilityLabel="Reason" placeholder="Reason for reporting" placeholderTextColor={colors.textMuted} value={reason} onChangeText={setReason} multiline style={styles.reason} />
      <ListItem icon="flag-outline" title="Report this member" subtitle="Send this profile to moderation" onPress={() => safety("/community/reports", { target_type: "user", target_id: userId, reason })} />
      <ListItem icon="ban-outline" title="Block this member" subtitle="Stop contact and hide their content" onPress={() => safety(`/community/blocks/${userId}`)} />
    </OverflowMenu>
  </KeyboardAvoidingView></SafeAreaView>;
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background }, loading: { padding: 18 }, messages: { flexGrow: 1, paddingHorizontal: 14, paddingVertical: 12, justifyContent: "flex-end" },
  messageRow: { flexDirection: "row", alignItems: "flex-end", gap: 7, marginVertical: 4 }, messageRowMine: { justifyContent: "flex-end" },
  bubble: { maxWidth: "78%", paddingHorizontal: 13, paddingTop: 9, paddingBottom: 6, borderRadius: 18 }, bubbleMine: { backgroundColor: colors.primary, borderBottomRightRadius: 6 }, bubbleTheirs: { backgroundColor: colors.surface, borderBottomLeftRadius: 6 },
  message: { color: colors.text, fontFamily: fonts.regular, fontSize: 14, lineHeight: 19 }, messageMine: { color: colors.white }, messageTime: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 8, marginTop: 4 }, messageTimeMine: { color: "rgba(255,255,255,.75)", textAlign: "right" },
  composer: { flexDirection: "row", alignItems: "flex-end", gap: 9, padding: 10, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border, backgroundColor: colors.surface },
  input: { flex: 1, maxHeight: 110, minHeight: 44, paddingHorizontal: 15, paddingVertical: 11, borderRadius: 20, backgroundColor: colors.surfaceAlt, color: colors.text, fontFamily: fonts.regular, fontSize: 14 },
  send: { width: 44, height: 44, borderRadius: 16, backgroundColor: colors.primary, alignItems: "center", justifyContent: "center" }, pressed: { opacity: .75 }, disabled: { opacity: .45 },
  reason: { minHeight: 76, borderRadius: 16, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, padding: 12, color: colors.text, textAlignVertical: "top", marginBottom: 6 },
});
