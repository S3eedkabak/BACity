import { useCallback, useEffect, useRef, useState } from "react";
import { FlatList, Linking, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { router, useLocalSearchParams } from "expo-router";
import { apiRequest } from "../../src/api/client";
import { follow } from "../../src/api/community";
import { EventCard } from "../../src/components/EventCard";
import { EmptyState } from "../../src/components/EmptyState";
import { ProfileRow, SkeletonList } from "../../src/components/SocialUI";
import { useAuthStore } from "../../src/store/authStore";
import { colors } from "../../src/theme/colors";
import { fonts } from "../../src/theme/fonts";
import type { EventCategory, EventListResponse } from "../../src/types/event";

type Domain = "events" | "places" | "people" | "organizers";
const DOMAINS: { id: Domain; label: string; icon: keyof typeof Ionicons.glyphMap }[] = [
  { id: "events", label: "Events", icon: "calendar-outline" }, { id: "places", label: "Places", icon: "location-outline" },
  { id: "people", label: "People", icon: "people-outline" }, { id: "organizers", label: "Organizers", icon: "business-outline" },
];
const CATEGORIES: EventCategory[] = ["Music", "Culture", "Nightlife", "Food & Drink", "Markets", "Workshops", "Family", "Other"];

export default function ExploreScreen() {
  const params = useLocalSearchParams<{ domain?: Domain }>(); const token = useAuthStore(state => state.token);
  const [domain, setDomain] = useState<Domain>(params.domain && DOMAINS.some(item => item.id === params.domain) ? params.domain : "events");
  const [query, setQuery] = useState(""); const [term, setTerm] = useState(""); const [category, setCategory] = useState<EventCategory | null>(null);
  const [items, setItems] = useState<any[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState(""); const [more, setMore] = useState(false); const request = useRef(0);
  useEffect(() => { if (params.domain && DOMAINS.some(item => item.id === params.domain)) setDomain(params.domain); }, [params.domain]);
  useEffect(() => { const timer = setTimeout(() => setTerm(query.trim()), 300); return () => clearTimeout(timer); }, [query]);
  const load = useCallback(async (append = false) => { const id = ++request.current; const offset = append ? items.length : 0; setLoading(true); setError(""); try {
    let result: any[];
    if (domain === "events") { if (term) result = await apiRequest<any[]>("/events/search", { params: { q: term, limit: 50 } }); else result = (await apiRequest<EventListResponse>("/events", { params: { category: category || undefined, offset, limit: 20 } })).items; }
    else if (domain === "places") result = await apiRequest<any[]>("/community/places", { params: { q: term, offset } });
    else if (domain === "people") result = token ? await apiRequest<any[]>("/community/people", { auth: true, params: { q: term, offset, limit: 20 } }) : [];
    else result = await apiRequest<any[]>("/community/organizations", { params: { q: term } });
    if (id === request.current) { setItems(current => append ? [...current, ...result] : result); setMore(((domain === "events" && !term) || domain === "people") && result.length === 20); }
  } catch (e: any) { if (id === request.current) setError(e.message); } finally { if (id === request.current) setLoading(false); } }, [category, domain, items.length, term, token]);
  useEffect(() => { setItems([]); void load(false); }, [domain, term, category, token]);
  async function followOrganizer(item: any) { try { await follow("organizer", item.id); } catch (e: any) { setError(e.message); } }

  return <SafeAreaView style={styles.safe} edges={["top"]}><FlatList data={items} keyExtractor={(item, index) => item.id || String(index)} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}
    ListHeaderComponent={<><Text style={styles.heading}>Explore</Text><View style={styles.search}><Ionicons name="search" size={20} color={colors.primaryDark} /><TextInput accessibilityLabel="Search BACity" placeholder={`Search ${domain}`} placeholderTextColor={colors.textMuted} value={query} onChangeText={setQuery} autoCorrect={false} style={styles.input} />{query ? <Pressable accessibilityLabel="Clear search" onPress={() => setQuery("")}><Ionicons name="close-circle" size={20} color={colors.textMuted} /></Pressable> : null}</View><FlatList horizontal data={DOMAINS} keyExtractor={item => item.id} showsHorizontalScrollIndicator={false} contentContainerStyle={styles.domains} renderItem={({ item }) => <Pressable onPress={() => { setDomain(item.id); setCategory(null); }} style={[styles.domain, domain === item.id && styles.domainActive]}><Ionicons name={item.icon} size={16} color={domain === item.id ? colors.white : colors.textMuted} /><Text style={[styles.domainText, domain === item.id && styles.domainTextActive]}>{item.label}</Text></Pressable>} />{domain === "events" && !term ? <FlatList horizontal data={CATEGORIES} keyExtractor={item => item} showsHorizontalScrollIndicator={false} contentContainerStyle={styles.categories} renderItem={({ item }) => <Pressable onPress={() => setCategory(category === item ? null : item)} style={[styles.category, category === item && styles.categoryActive]}><Text style={[styles.categoryText, category === item && styles.categoryTextActive]}>{item}</Text></Pressable>} /> : null}<View style={styles.resultHeader}><Text style={styles.resultTitle}>{term ? `Results for “${term}”` : domain === "events" ? "Happening in Bratislava" : `Discover ${domain}`}</Text><Text style={styles.count}>{items.length}</Text></View>{error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}{loading && !items.length ? <SkeletonList rows={4} /> : null}{domain === "people" && !token ? <EmptyState title="Sign in to find people" subtitle="Member discovery respects profile privacy and block settings." action="Sign in" onAction={() => router.push({ pathname: "/auth", params: { mode: "login" } })} /> : null}</>}
    ListEmptyComponent={!loading && !error && !(domain === "people" && !token) ? <EmptyState title="No matches found" subtitle="Try another search or browse a different section." /> : null}
    renderItem={({ item }) => domain === "events" ? <EventCard event={item} /> : domain === "people" ? <ProfileRow profile={item} subtitle={`${item.neighborhood || item.city || "Bratislava"} · ${item.reputation_level}`} onPress={() => router.push(`/member/${item.id}`)} /> : domain === "places" ? <Pressable onPress={() => router.push(`/place/${item.id}`)} style={({ pressed }) => [styles.place, pressed && styles.pressed]}><View style={styles.placeIcon}><Ionicons name="location" size={20} color={colors.primaryDark} /></View><View style={styles.placeCopy}><Text style={styles.placeTitle}>{item.name}</Text><Text style={styles.placeCategory}>{item.category || "Local place"}</Text><Text style={styles.placeAddress} numberOfLines={1}>{item.address}</Text></View><Ionicons name="chevron-forward" size={17} color={colors.textMuted} /></Pressable> : <View style={styles.organizer}><View style={styles.organizerTop}><View style={styles.orgIcon}><Ionicons name="business-outline" size={20} color={colors.primaryDark} /></View><View style={styles.placeCopy}><Text style={styles.placeTitle}>{item.name}</Text><Text style={styles.placeCategory}>{item.verified ? "Verified organizer" : "Community organizer"}</Text></View></View>{item.description ? <Text style={styles.orgDescription} numberOfLines={3}>{item.description}</Text> : null}<View style={styles.orgActions}><Text style={styles.link} onPress={() => followOrganizer(item)}>Follow</Text>{item.website ? <Text style={styles.link} onPress={() => Linking.openURL(item.website)}>Website</Text> : null}<Text style={styles.link} onPress={() => router.push({ pathname: "/organizer", params: { claim: item.id } })}>Claim / manage</Text></View></View>}
    ListFooterComponent={more ? <Pressable disabled={loading} onPress={() => load(true)} style={styles.loadMore}><Text style={styles.link}>{loading ? "Loading…" : "Load more"}</Text></Pressable> : null}
  /></SafeAreaView>;
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background }, content: { paddingHorizontal: 18, paddingTop: 12, paddingBottom: 92, flexGrow: 1 }, heading: { color: colors.text, fontFamily: fonts.black, fontSize: 34, letterSpacing: -1 },
  search: { height: 56, marginTop: 14, borderRadius: 20, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: 15 }, input: { flex: 1, color: colors.text, fontFamily: fonts.regular, fontSize: 14 },
  domains: { gap: 8, paddingVertical: 16 }, domain: { height: 38, paddingHorizontal: 13, borderRadius: 15, backgroundColor: colors.surface, flexDirection: "row", alignItems: "center", gap: 6, borderWidth: 1, borderColor: colors.border }, domainActive: { backgroundColor: colors.primary, borderColor: colors.primary }, domainText: { color: colors.textMuted, fontFamily: fonts.semibold, fontSize: 10 }, domainTextActive: { color: colors.white },
  categories: { gap: 7, paddingBottom: 14 }, category: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 99, backgroundColor: colors.primarySoft }, categoryActive: { backgroundColor: colors.text }, categoryText: { color: colors.primaryDark, fontFamily: fonts.medium, fontSize: 9 }, categoryTextActive: { color: colors.white },
  resultHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }, resultTitle: { color: colors.text, fontFamily: fonts.black, fontSize: 18 }, count: { color: colors.textMuted, fontFamily: fonts.semibold, fontSize: 11 }, error: { color: colors.danger, fontFamily: fonts.medium, paddingVertical: 12 },
  place: { minHeight: 82, flexDirection: "row", alignItems: "center", gap: 12, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border }, pressed: { opacity: .68 }, placeIcon: { width: 50, height: 50, borderRadius: 18, backgroundColor: colors.primarySoft, alignItems: "center", justifyContent: "center" }, placeCopy: { flex: 1 }, placeTitle: { color: colors.text, fontFamily: fonts.semibold, fontSize: 14 }, placeCategory: { color: colors.primaryDark, fontFamily: fonts.medium, fontSize: 9, marginTop: 2 }, placeAddress: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 10, marginTop: 3 },
  organizer: { paddingVertical: 16, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border }, organizerTop: { flexDirection: "row", alignItems: "center", gap: 12 }, orgIcon: { width: 50, height: 50, borderRadius: 18, backgroundColor: colors.primarySoft, alignItems: "center", justifyContent: "center" }, orgDescription: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 11, lineHeight: 16, marginTop: 9 }, orgActions: { flexDirection: "row", flexWrap: "wrap", gap: 18, marginTop: 11 }, link: { color: colors.primaryDark, fontFamily: fonts.semibold, fontSize: 11 }, loadMore: { alignItems: "center", padding: 18 },
});
