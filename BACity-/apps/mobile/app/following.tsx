import { themedStyles, useThemeRevision } from '../src/theme/appearance';
import { FollowAction } from '../src/components/interactions/FollowAction';
import { View as Row } from 'react-native';
import { useState } from "react";
import { FlatList, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from '../src/components/navigation/ContentSafeArea';
import { router } from "expo-router";
import { apiRequest } from "../src/api/client";
import { Chip } from "../src/components/CommunityUI";
import { ListItem, ProfileRow, ScreenHeader } from "../src/components/SocialUI";
import { EmptyState } from "../src/components/EmptyState";
import { colors } from "../src/theme/colors";
import { fonts } from "../src/theme/fonts";
import { useAuthStore } from "../src/store/authStore";

const TYPES = ["user", "guide", "organizer", "venue", "category", "neighborhood"] as const;
export default function FollowingDiscovery() {
  useThemeRevision();
  const user = useAuthStore(state => state.user);
  const [type, setType] = useState<(typeof TYPES)[number]>("user"); const [query, setQuery] = useState(""); const [items, setItems] = useState<any[]>([]); const [loading, setLoading] = useState(false); const [notice, setNotice] = useState("");
  async function search() { setLoading(true); setNotice(""); try { setItems(await apiRequest<any[]>("/community/follow-targets", { auth: true, params: { target_type: type, q: query, limit: 20 } })); } catch (e: any) { setNotice(e.message); } finally { setLoading(false); } }

  return <SafeAreaView style={styles.safe} edges={["top", "bottom"]}><ScreenHeader title="Find people & interests" right={user ? <Text style={styles.manage} onPress={() => router.push("/social/following")}>Manage</Text> : undefined} />{!user ? <EmptyState title="Sign in to follow local life" subtitle="Follow people, organizers, venues and neighborhoods." action="Sign in" onAction={() => router.push({ pathname: "/auth", params: { mode: "login" } })} /> : <FlatList data={items} keyExtractor={item => `${item.target_type}:${item.target_id}`} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled" ListHeaderComponent={<><Text style={styles.intro}>Shape your city feed with people, places and topics you care about.</Text><View style={styles.chips}>{TYPES.map(value => <Chip key={value} title={value[0].toUpperCase() + value.slice(1)} active={type === value} onPress={() => { setType(value); setItems([]); }} />)}</View><View style={styles.search}><TextInput accessibilityLabel={`Search ${type}`} placeholder={`Search ${type}s`} placeholderTextColor={colors.textMuted} value={query} onChangeText={setQuery} onSubmitEditing={search} style={styles.input} /><Text style={styles.searchAction} onPress={search}>{loading ? "…" : "Search"}</Text></View>{notice ? <Text style={styles.notice}>{notice}</Text> : null}</>} ListEmptyComponent={!loading ? <EmptyState title="Find something local" subtitle="Search by name, or leave the field empty to browse." action="Browse" onAction={search} /> : null} renderItem={({ item }) => <Row style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}><Row style={{ flex: 1 }}>{["user", "guide"].includes(item.target_type) ? <ProfileRow profile={{ id: item.target_id, display_name: item.name, avatar_url: item.avatar_url }} subtitle={item.subtitle} onPress={() => router.push(`/member/${item.target_id}`)} /> : <ListItem icon={item.target_type === "organizer" ? "business-outline" : item.target_type === "venue" ? "location-outline" : "pricetag-outline"} title={item.name} subtitle={item.subtitle} />}</Row><FollowAction type={item.target_type} id={item.target_id} /></Row>} />}</SafeAreaView>;
}
const styles = themedStyles(() => ({ safe: { flex: 1, backgroundColor: colors.background }, content: { width: '100%', maxWidth: 760, alignSelf: 'center', paddingHorizontal: 18, paddingBottom: 28, flexGrow: 1 }, intro: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 13, lineHeight: 19, marginVertical: 8 }, chips: { flexDirection: "row", flexWrap: "wrap", gap: 7, marginVertical: 14 }, search: { height: 52, flexDirection: "row", alignItems: "center", borderRadius: 18, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 14 }, input: { flex: 1, color: colors.text, fontFamily: fonts.regular }, searchAction: { color: colors.primaryDark, fontFamily: fonts.semibold, fontWeight: '600', padding: 8 }, notice: { color: colors.primaryDark, fontFamily: fonts.medium, marginTop: 10 }, manage: { color: colors.primaryDark, fontFamily: fonts.semibold, fontWeight: '600', fontSize: 12, width: 54 }, follow: { color: colors.primaryDark, fontFamily: fonts.semibold, fontWeight: '600', padding: 10 } }));
