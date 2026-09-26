import { useEffect, useState } from "react";
import { FlatList, Linking, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { apiRequest } from "../src/api/client";
import { EmptyState } from "../src/components/EmptyState";
import { ListItem, ScreenHeader, SkeletonList } from "../src/components/SocialUI";
import { Button } from "../src/components/CommunityUI";
import { colors } from "../src/theme/colors";
import { fonts } from "../src/theme/fonts";
import { useAuthStore } from "../src/store/authStore";

export default function ActivityScreen() {
  const user = useAuthStore(state => state.user);
  const [items, setItems] = useState<any[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState(""); const [reason, setReason] = useState("");
  async function load(offset = 0) { setLoading(true); try { const page = await apiRequest<any[]>("/community/submissions", { auth: true, params: { offset } }); setItems(current => offset ? [...current, ...page] : page); setError(""); } catch (e: any) { setError(e.message); } finally { setLoading(false); } }
  useEffect(() => { if (user) void load(); else setLoading(false); }, [user?.id]);
  async function appeal(id: string) { try { await apiRequest(`/community/submissions/${id}/appeal`, { method: "POST", auth: true, body: { reason } }); setReason(""); await load(); } catch (e: any) { setError(e.message); } }
  return <SafeAreaView style={styles.safe} edges={["top", "bottom"]}><ScreenHeader title="Your activity" />{!user ? <EmptyState title="Sign in to see your activity" subtitle="Contribution decisions and appeals are linked to your account." action="Sign in" onAction={() => router.push({ pathname: "/auth", params: { mode: "login" } })} /> : <>{error ? <Text style={styles.error}>{error}</Text> : null}{loading && !items.length ? <View style={styles.content}><SkeletonList /></View> : <FlatList data={items} keyExtractor={item => item.id} contentContainerStyle={styles.content} ListEmptyComponent={<EmptyState title="No contributions yet" subtitle="Events, places and utilities you submit will be tracked here." />} renderItem={({ item }) => <View style={styles.item}><ListItem icon={item.kind === "event" ? "calendar-outline" : item.kind === "place" ? "location-outline" : "construct-outline"} title={item.payload?.title || item.payload?.name || item.kind} subtitle={`${item.state} · ${new Date(item.created_at).toLocaleDateString()}`} />{item.decision_reason ? <Text style={styles.note}>{item.decision_reason}</Text> : null}{item.payload?.source_url ? <Text style={styles.link} onPress={() => Linking.openURL(item.payload.source_url)}>View submitted source</Text> : null}{item.state === "rejected" && !item.appeal ? <><TextInput accessibilityLabel="Appeal reason" placeholder="Explain why this should be reconsidered" placeholderTextColor={colors.textMuted} value={reason} onChangeText={setReason} multiline style={styles.input} /><Button title="Appeal decision" onPress={() => appeal(item.id)} /></> : null}{item.appeal ? <Text style={styles.note}>Appeal: {item.appeal}</Text> : null}</View>} ListFooterComponent={items.length > 0 && items.length % 100 === 0 ? <Text style={styles.more} onPress={() => load(items.length)}>Load more</Text> : null} />}</>}</SafeAreaView>;
}
const styles = StyleSheet.create({ safe: { flex: 1, backgroundColor: colors.background }, content: { paddingHorizontal: 18, paddingBottom: 28, flexGrow: 1 }, item: { paddingBottom: 14 }, error: { marginHorizontal: 18, padding: 12, color: colors.danger }, note: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 11, lineHeight: 16, marginLeft: 56 }, link: { color: colors.primaryDark, fontFamily: fonts.semibold, fontSize: 11, marginLeft: 56, marginTop: 6 }, input: { minHeight: 78, marginVertical: 10, borderWidth: 1, borderColor: colors.border, borderRadius: 16, padding: 12, color: colors.text, textAlignVertical: "top" }, more: { color: colors.primaryDark, textAlign: "center", padding: 18 } });
