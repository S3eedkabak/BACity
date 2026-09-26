import { useEffect, useState } from "react";
import { FlatList, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { apiRequest } from "../src/api/client";
import { EmptyState } from "../src/components/EmptyState";
import { ListItem, ScreenHeader, SkeletonList } from "../src/components/SocialUI";
import { colors } from "../src/theme/colors";
import { fonts } from "../src/theme/fonts";
import { useAuthStore } from "../src/store/authStore";

export default function BlockedScreen() {
  const user = useAuthStore(state => state.user);
  const [items, setItems] = useState<any[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState("");
  async function load() { setLoading(true); try { setItems(await apiRequest<any[]>("/community/blocks", { auth: true })); setError(""); } catch (e: any) { setError(e.message); } finally { setLoading(false); } }
  useEffect(() => { if (user) void load(); else setLoading(false); }, [user?.id]);
  async function unblock(id: string) { try { await apiRequest(`/community/blocks/${id}`, { method: "DELETE", auth: true }); await load(); } catch (e: any) { setError(e.message); } }
  return <SafeAreaView style={styles.safe} edges={["top", "bottom"]}><ScreenHeader title="Blocked users" />{!user ? <EmptyState title="Sign in to manage blocked users" action="Sign in" onAction={() => router.push({ pathname: "/auth", params: { mode: "login" } })} /> : <>{error ? <Text style={styles.error}>{error}</Text> : null}{loading ? <View style={styles.content}><SkeletonList rows={3} /></View> : <FlatList data={items} keyExtractor={item => item.id} contentContainerStyle={styles.content} ListEmptyComponent={<EmptyState title="No blocked users" subtitle="People you block will appear here." />} renderItem={({ item }) => <ListItem icon="ban-outline" title="Blocked member" subtitle={`ID ${String(item.blocked_id).slice(0, 8)}…`} trailing={<Text style={styles.unblock} onPress={() => unblock(item.blocked_id)}>Unblock</Text>} />} />}</>}</SafeAreaView>;
}
const styles = StyleSheet.create({ safe: { flex: 1, backgroundColor: colors.background }, content: { paddingHorizontal: 18, flexGrow: 1 }, error: { color: colors.danger, paddingHorizontal: 18 }, unblock: { color: colors.primaryDark, fontFamily: fonts.semibold, fontSize: 11, padding: 10 } });
