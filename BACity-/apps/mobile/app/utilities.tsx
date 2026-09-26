import { useEffect, useState } from "react";
import { FlatList, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { apiRequest } from "../src/api/client";
import { Chip } from "../src/components/CommunityUI";
import { EmptyState } from "../src/components/EmptyState";
import { ListItem, ScreenHeader, SkeletonList } from "../src/components/SocialUI";
import { colors } from "../src/theme/colors";
import { fonts } from "../src/theme/fonts";

const KINDS = [{ id: "toilet", label: "Toilets" }, { id: "water_fountain", label: "Water" }, { id: "bike_repair", label: "Bike repair" }, { id: "charging", label: "Charging" }, { id: "wifi", label: "Wi‑Fi" }, { id: "bench", label: "Benches" }, { id: "playground", label: "Playgrounds" }, { id: "dog_park", label: "Dog parks" }, { id: "recycling", label: "Recycling" }, { id: "accessible_entrance", label: "Accessible" }, { id: "parking", label: "Parking" }, { id: "locker", label: "Lockers" }];
export default function UtilitiesScreen() {
  const [kind, setKind] = useState("toilet"); const [items, setItems] = useState<any[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState("");
  async function load() { setLoading(true); try { setItems(await apiRequest<any[]>("/community/utilities", { params: { kind } })); setError(""); } catch (e: any) { setError(e.message); } finally { setLoading(false); } }
  useEffect(() => { void load(); }, [kind]);
  return <SafeAreaView style={styles.safe} edges={["top", "bottom"]}><ScreenHeader title="City utilities" /><FlatList data={items} keyExtractor={item => item.id} contentContainerStyle={styles.content} ListHeaderComponent={<><Text style={styles.intro}>Useful public facilities and their latest community-confirmed status.</Text><View style={styles.kinds}>{KINDS.map(item => <Chip key={item.id} title={item.label} active={kind === item.id} onPress={() => setKind(item.id)} />)}</View>{error ? <Text style={styles.error}>{error}</Text> : null}{loading ? <SkeletonList rows={3} /> : null}</>} ListEmptyComponent={!loading ? <EmptyState title="No utilities in this category" subtitle="Community and city data will appear here when available." /> : null} renderItem={({ item }) => <ListItem icon={kind === "toilet" ? "business-outline" : "construct-outline"} title={item.name} subtitle={`${item.address || "Bratislava"} · ${String(item.operational_status || "unknown").replaceAll("_", " ")}`} onPress={() => router.push({ pathname: "/utility/[id]", params: { id: item.id, kind } })} />} /></SafeAreaView>;
}
const styles = StyleSheet.create({ safe: { flex: 1, backgroundColor: colors.background }, content: { paddingHorizontal: 18, paddingBottom: 28, flexGrow: 1 }, intro: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 13, lineHeight: 19, marginVertical: 8 }, kinds: { flexDirection: "row", flexWrap: "wrap", gap: 7, marginVertical: 12 }, error: { color: colors.danger, marginVertical: 8 } });
