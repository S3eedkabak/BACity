import { useEffect, useState } from "react";
import { ActivityIndicator, KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, View } from "react-native";
import { AnimatedPressable as Pressable } from '../src/components/motion/Motion';
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { AppIcon } from "../src/components/AppIcon";
import { areaWatchesApi, WatchRadius } from "../src/api/areaWatches";
import { areaWatchRoute, resolveAreaWatchView, totalUnseen, validWatchCoordinates } from "../src/areaWatch/presentation";
import { AreaWatchMapPicker } from "../src/components/AreaWatchMapPicker";
import { Button, Chip, Field } from "../src/components/CommunityUI";
import { EmptyState } from "../src/components/EmptyState";
import { ScreenHeader } from "../src/components/SocialUI";
import { useAreaWatchMutation, useAreaWatches } from "../src/hooks/useAreaWatches";
import { usePlusGate } from "../src/plus/usePlusGate";
import { useRecommendationLocation } from "../src/recommendations/useRecommendationLocation";
import { colors } from "../src/theme/colors";
import { fonts } from "../src/theme/fonts";
import type { EventCategory } from "../src/types/event";
import { PremiumIntro } from '../src/components/PremiumUI';
import { Disclosure } from '../src/components/CommunityUI';

const CATEGORIES: EventCategory[] = ["Music", "Culture", "Arts", "Nightlife", "Theatre", "Family", "Community", "Food & Drink"];
const RADII: WatchRadius[] = [1, 2, 5];

export default function AreaWatchesScreen() {
  const gate = usePlusGate();
  const allowed = gate.decision === "allow";
  const query = useAreaWatches(allowed);
  const mutation = useAreaWatchMutation();
  const location = useRecommendationLocation(allowed);
  const [name, setName] = useState("City Centre");
  const [latitude, setLatitude] = useState(48.1486);
  const [longitude, setLongitude] = useState(17.1077);
  const [radius, setRadius] = useState<WatchRadius>(2);
  const [categories, setCategories] = useState<EventCategory[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const watches = query.data ?? [];
  const state = resolveAreaWatchView(gate.decision, query.isError, watches.length);
  const locationNotice = location.status === "blocked"
    ? "Location permission is blocked. Choose the point manually or enable permission in Settings."
    : location.status === "denied"
      ? "Location permission was denied. You can still choose the point manually."
      : ["unavailable", "timeout", "error", "outside-area"].includes(location.status)
        ? "Current location is unavailable. Choose the point manually or retry."
        : null;

  useEffect(() => { if (location.coordinates) { setLatitude(location.coordinates.latitude); setLongitude(location.coordinates.longitude); } }, [location.coordinates]);
  function toggle(category: EventCategory) { setCategories(current => current.includes(category) ? current.filter(item => item !== category) : current.length < 6 ? [...current, category] : current); }
  async function create() {
    if (!validWatchCoordinates(latitude, longitude)) { setNotice("Choose a point inside Bratislava."); return; }
    setNotice(null);
    try {
      const created = await mutation.mutateAsync(() => areaWatchesApi.create({ name, center_latitude: latitude, center_longitude: longitude, radius_km: radius, categories })) as Awaited<ReturnType<typeof areaWatchesApi.create>>;
      router.push(areaWatchRoute(created.id));
    } catch (error) { setNotice((error as Error).message); }
  }

  if (state === "loading") return <SafeAreaView style={styles.safe}><ScreenHeader title="Area Watch" /><View style={styles.center}><ActivityIndicator color={colors.primary} /></View></SafeAreaView>;
  if (state === "paywall") return <SafeAreaView style={styles.safe}><ScreenHeader title="Area Watch" /><EmptyState title="Area Watch is a BACity+ feature" subtitle="Watch newly discovered activity in a private area you choose." action="View BACity+" onAction={() => router.push({ pathname: "/plus", params: { feature: "area_watch", ...(gate.decision === "error" ? { unavailable: "1" } : {}) } })} /></SafeAreaView>;

  return <SafeAreaView style={styles.safe} edges={["top", "bottom"]}><ScreenHeader title="Area Watch" /><KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}><ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
    <PremiumIntro icon="radio-outline" title="Keep a little eye on your city." subtitle={`Private areas you choose. No background tracking. ${totalUnseen(watches)} new events are waiting.`} />
    {state === "error" ? <EmptyState title="Area Watch couldn't load" action="Try again" onAction={() => void query.refetch()} /> : null}
    {watches.map(watch => <Pressable key={watch.id} onPress={() => router.push(areaWatchRoute(watch.id))} style={({ pressed }) => [styles.watch, pressed && styles.pressed]}><View style={styles.watchIcon}><AppIcon name="radio-outline" size={20} color={colors.primaryDark} /></View><View style={styles.watchCopy}><Text style={styles.watchName}>{watch.name}</Text><Text style={styles.watchMeta}>{watch.radius_km} km · {watch.categories.length ? watch.categories.join(" + ") : "All categories"}</Text></View>{watch.unseen_count ? <View style={styles.badge}><Text style={styles.badgeText}>{watch.unseen_count}</Text></View> : null}<AppIcon name="chevron-forward" size={18} color={colors.textMuted} /></Pressable>)}
    {state === "empty" ? <EmptyState title="No watched areas yet" subtitle="Choose a meaningful point and BACity will surface newly discovered events nearby." /> : null}
    <Disclosure title="Choose a new area" icon="add-circle-outline" initiallyOpen><AreaWatchMapPicker latitude={latitude} longitude={longitude} radiusKm={radius} onChange={(lat, lng) => { setLatitude(lat); setLongitude(lng); }} /><Pressable onPress={() => void location.enable()} style={({ pressed }) => [styles.locationButton, pressed && styles.pressed]}><AppIcon name="locate-outline" size={16} color={colors.primaryDark} /><Text style={styles.locationText}>{location.status === "locating" ? "Finding approximate location…" : "Use approximate current location"}</Text></Pressable>{locationNotice ? <Text accessibilityRole="alert" style={styles.locationNotice}>{locationNotice}</Text> : null}<Field label="Watch name" value={name} onChange={setName} /><Disclosure title="Exact coordinates" icon="locate-outline"><View style={styles.split}><View style={styles.flex}><Field label="Latitude" value={String(latitude)} onChange={value => setLatitude(Number(value))} /></View><View style={styles.flex}><Field label="Longitude" value={String(longitude)} onChange={value => setLongitude(Number(value))} /></View></View></Disclosure><Text style={styles.label}>RADIUS</Text><View style={styles.chips}>{RADII.map(value => <Chip key={value} title={`${value} km`} active={radius === value} onPress={() => setRadius(value)} />)}</View><Text style={styles.label}>OPTIONAL CATEGORIES</Text><View style={styles.chips}>{CATEGORIES.map(category => <Chip key={category} title={category} active={categories.includes(category)} onPress={() => toggle(category)} />)}</View><Button title="Create Area Watch" busy={mutation.isPending} onPress={create} />{notice ? <Text accessibilityRole="alert" style={styles.error}>{notice}</Text> : null}</Disclosure>
  </ScrollView></KeyboardAvoidingView></SafeAreaView>;
}

const styles = StyleSheet.create({ safe: { flex: 1, backgroundColor: colors.background }, center: { flex: 1, alignItems: "center", justifyContent: "center" }, content: { width: '100%', maxWidth: 760, alignSelf: 'center', paddingHorizontal: 18, paddingBottom: 44 }, heading: { color: colors.text, fontFamily: fonts.black, fontWeight: '800', fontSize: 25, marginTop: 10 }, subtitle: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 12, lineHeight: 18, marginTop: 6, marginBottom: 14 }, watch: { minHeight: 72, padding: 12, marginBottom: 8, borderRadius: 19, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, flexDirection: "row", alignItems: "center", gap: 10 }, watchIcon: { width: 42, height: 42, borderRadius: 14, backgroundColor: colors.primarySoft, alignItems: "center", justifyContent: "center" }, watchCopy: { flex: 1 }, watchName: { color: colors.text, fontFamily: fonts.black, fontWeight: '800', fontSize: 14 }, watchMeta: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 12, marginTop: 4 }, badge: { minWidth: 24, height: 24, paddingHorizontal: 6, borderRadius: 12, backgroundColor: colors.primary, alignItems: "center", justifyContent: "center" }, badgeText: { color: colors.white, fontFamily: fonts.black, fontWeight: '800', fontSize: 12 }, pressed: { opacity: .7 }, card: { marginTop: 18, padding: 15, gap: 11, borderRadius: 22, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border }, cardTitle: { color: colors.text, fontFamily: fonts.black, fontWeight: '800', fontSize: 17 }, split: { flexDirection: "row", gap: 8 }, flex: { flex: 1 }, label: { color: colors.textMuted, fontFamily: fonts.black, fontWeight: '800', fontSize: 12, letterSpacing: 1 }, chips: { flexDirection: "row", flexWrap: "wrap", gap: 7 }, locationButton: { minHeight: 44, borderRadius: 14, backgroundColor: colors.primarySoft, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 7 }, locationText: { color: colors.primaryDark, fontFamily: fonts.semibold, fontWeight: '600', fontSize: 12 }, locationNotice: { color: colors.textMuted, fontFamily: fonts.medium, fontSize: 12, lineHeight: 18 }, error: { color: colors.danger, fontFamily: fonts.medium, fontSize: 12 } });
