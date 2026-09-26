import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "../src/api/client";
import { EmptyState } from "../src/components/EmptyState";
import { ScreenHeader, SkeletonList } from "../src/components/SocialUI";
import { useAuthStore } from "../src/store/authStore";
import { colors } from "../src/theme/colors";
import { fonts } from "../src/theme/fonts";

export default function CollectionsScreen() {
  const user = useAuthStore(state => state.user);
  const query = useQuery({ queryKey: ["collections"], queryFn: () => apiRequest<any[]>("/community/collections", { auth: true }), enabled: !!user });
  function open(item: any) { if (item.type === "event") router.push(`/event/${item.id}`); else if (item.type === "place") router.push(`/place/${item.id}`); else router.push(`/utility/${item.id}`); }
  return <SafeAreaView style={styles.safe} edges={["top", "bottom"]}><ScreenHeader title="Collections" right={user ? <Pressable accessibilityRole="button" accessibilityLabel="Create collection" onPress={() => router.push("/collection")} style={styles.add}><Ionicons name="add" size={21} color={colors.primaryDark} /></Pressable> : undefined} />
    {!user ? <EmptyState title="Sign in to use collections" subtitle="Create personal lists of events, places and utilities." action="Sign in" onAction={() => router.push({ pathname: "/auth", params: { mode: "login" } })} /> :
    query.isPending ? <View style={styles.content}><SkeletonList rows={4} /></View> : query.isError ? <EmptyState title="Collections couldn't load" subtitle={query.error.message} action="Try again" onAction={() => query.refetch()} /> : <FlatList data={query.data} keyExtractor={item => item.id} contentContainerStyle={styles.content} refreshing={query.isRefetching} onRefresh={query.refetch} ListEmptyComponent={<EmptyState title="No collections yet" subtitle="Group events, places and useful city spots into a personal list." action="Create collection" onAction={() => router.push("/collection")} />} renderItem={({ item }) => <View style={styles.collection}><View style={styles.collectionTop}><View><Text style={styles.title}>{item.title}</Text><Text style={styles.meta}>{item.public ? "Public collection" : "Private collection"} · {item.items.length} items</Text></View><Ionicons name="albums-outline" size={22} color={colors.primaryDark} /></View>{item.description ? <Text style={styles.description}>{item.description}</Text> : null}<View style={styles.items}>{item.items.slice(0, 4).map((entry: any) => <Pressable key={`${entry.type}:${entry.id}`} onPress={() => open(entry)} style={styles.item}><Ionicons name={entry.type === "event" ? "calendar-outline" : entry.type === "place" ? "location-outline" : "construct-outline"} size={15} color={colors.primaryDark} /><Text style={styles.itemText}>{entry.type}</Text></Pressable>)}</View></View>} />}
  </SafeAreaView>;
}
const styles = StyleSheet.create({ safe: { flex: 1, backgroundColor: colors.background }, content: { paddingHorizontal: 18, paddingBottom: 28, gap: 12, flexGrow: 1 }, add: { width: 44, height: 44, alignItems: "center", justifyContent: "center" }, collection: { paddingVertical: 17, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border }, collectionTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" }, title: { color: colors.text, fontFamily: fonts.black, fontSize: 18 }, meta: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 10, marginTop: 3 }, description: { color: colors.text, fontFamily: fonts.regular, fontSize: 12, lineHeight: 18, marginTop: 9 }, items: { flexDirection: "row", flexWrap: "wrap", gap: 7, marginTop: 12 }, item: { flexDirection: "row", alignItems: "center", gap: 5, paddingHorizontal: 10, paddingVertical: 8, borderRadius: 13, backgroundColor: colors.primarySoft }, itemText: { color: colors.primaryDark, fontFamily: fonts.semibold, fontSize: 9 } });
