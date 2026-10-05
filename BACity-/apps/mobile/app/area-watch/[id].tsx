import { useEffect, useRef, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router, useLocalSearchParams } from "expo-router";
import { areaWatchesApi, WatchRadius } from "../../src/api/areaWatches";
import { Button, Chip } from "../../src/components/CommunityUI";
import { EmptyState } from "../../src/components/EmptyState";
import { EventCard } from "../../src/components/EventCard";
import { ScreenHeader } from "../../src/components/SocialUI";
import { useAreaWatch, useAreaWatchFeed, useAreaWatchMutation } from "../../src/hooks/useAreaWatches";
import { usePlusGate } from "../../src/plus/usePlusGate";
import { colors } from "../../src/theme/colors";
import { fonts } from "../../src/theme/fonts";
import type { EventCategory } from "../../src/types/event";

const CATEGORIES: EventCategory[] = ["Music", "Culture", "Arts", "Nightlife", "Theatre", "Family", "Community", "Food & Drink"];
const RADII: WatchRadius[] = [1, 2, 5];

export default function AreaWatchDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const gate = usePlusGate();
  const allowed = gate.decision === "allow";
  const watchQuery = useAreaWatch(id ?? "", allowed);
  const feed = useAreaWatchFeed(id ?? "", allowed);
  const mutation = useAreaWatchMutation(id);
  const [radius, setRadius] = useState<WatchRadius>(2);
  const [categories, setCategories] = useState<EventCategory[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const marked = useRef<string | null>(null);
  const watch = watchQuery.data;
  const firstPage = feed.data?.pages[0];
  const items = feed.data?.pages.flatMap(page => page.items) ?? [];
  useEffect(() => { if (watch) { setRadius(watch.radius_km as WatchRadius); setCategories(watch.categories); } }, [watch]);
  useEffect(() => { const watermark = firstPage?.response_watermark; if (!watermark || marked.current === watermark || !id) return; marked.current = watermark; void areaWatchesApi.seen(id, watermark); }, [firstPage?.response_watermark, id]);
  function toggle(category: EventCategory) { setCategories(current => current.includes(category) ? current.filter(item => item !== category) : current.length < 6 ? [...current, category] : current); }
  async function run(work: () => Promise<unknown>, success?: string) { setNotice(null); try { await mutation.mutateAsync(work); if (success) setNotice(success); } catch (error) { setNotice((error as Error).message); } }

  if (gate.decision === "loading") return <SafeAreaView style={styles.safe}><ScreenHeader title="Area Watch" /><View style={styles.center}><ActivityIndicator color={colors.primary} /></View></SafeAreaView>;
  if (!allowed) return <SafeAreaView style={styles.safe}><ScreenHeader title="Area Watch" /><EmptyState title="BACity+ required" subtitle="Your saved watch remains private and will be available if BACity+ is restored." action="View BACity+" onAction={() => router.push({ pathname: "/plus", params: { feature: "area_watch", ...(gate.decision === "error" ? { unavailable: "1" } : {}) } })} /></SafeAreaView>;
  if (watchQuery.isPending || feed.isPending) return <SafeAreaView style={styles.safe}><ScreenHeader title="Area Watch" /><View style={styles.center}><ActivityIndicator color={colors.primary} /></View></SafeAreaView>;
  if (watchQuery.isError || feed.isError || !watch) return <SafeAreaView style={styles.safe}><ScreenHeader title="Area Watch" /><EmptyState title="Area Watch unavailable" action="Try again" onAction={() => { void watchQuery.refetch(); void feed.refetch(); }} /></SafeAreaView>;

  return <SafeAreaView style={styles.safe} edges={["top", "bottom"]}><ScreenHeader title={watch.name} /><ScrollView contentContainerStyle={styles.content}><Text style={styles.heading}>{watch.unseen_count} new nearby</Text><Text style={styles.subtitle}>Newly discovered in the last {firstPage?.lookback_days ?? 30} days · {watch.radius_km} km radius</Text>
    <View style={styles.panel}><Text style={styles.panelTitle}>Watch settings</Text><Text style={styles.label}>RADIUS</Text><View style={styles.chips}>{RADII.map(value => <Chip key={value} title={`${value} km`} active={radius === value} onPress={() => setRadius(value)} />)}</View><Text style={styles.label}>CATEGORIES</Text><View style={styles.chips}>{CATEGORIES.map(category => <Chip key={category} title={category} active={categories.includes(category)} onPress={() => toggle(category)} />)}</View><Button title="Save changes" busy={mutation.isPending} onPress={() => run(() => areaWatchesApi.update(watch.id, { radius_km: radius, categories }), "Watch updated.")} /></View>
    <Text style={styles.section}>NEWLY DISCOVERED</Text>{items.length ? items.map(item => <EventCard key={item.event.id} event={item.event} explanation={item.explanations[0]} />) : <EmptyState title="Nothing new in this area" subtitle="BACity will show real newly discovered events here when they appear." />}
    {feed.hasNextPage ? <Button title="Load more" busy={feed.isFetchingNextPage} onPress={() => void feed.fetchNextPage()} /> : null}
    {notice ? <Text accessibilityRole="alert" style={styles.notice}>{notice}</Text> : null}
    <Pressable style={styles.delete} onPress={() => run(async () => { await areaWatchesApi.remove(watch.id); router.replace("/area-watches"); })}><Text style={styles.deleteText}>Delete watched area</Text></Pressable>
  </ScrollView></SafeAreaView>;
}

const styles = StyleSheet.create({ safe: { flex: 1, backgroundColor: colors.background }, center: { flex: 1, alignItems: "center", justifyContent: "center" }, content: { width: '100%', maxWidth: 760, alignSelf: 'center', paddingHorizontal: 18, paddingBottom: 44 }, heading: { color: colors.text, fontFamily: fonts.black, fontWeight: '800', fontSize: 25, marginTop: 10 }, subtitle: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 12, marginTop: 5 }, panel: { marginTop: 18, padding: 15, borderRadius: 22, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, gap: 10 }, panelTitle: { color: colors.text, fontFamily: fonts.black, fontWeight: '800', fontSize: 16 }, label: { color: colors.textMuted, fontFamily: fonts.black, fontWeight: '800', fontSize: 12, letterSpacing: 1 }, chips: { flexDirection: "row", flexWrap: "wrap", gap: 7 }, section: { color: colors.textMuted, fontFamily: fonts.black, fontWeight: '800', fontSize: 12, letterSpacing: 1.2, marginTop: 24, marginBottom: 10 }, notice: { color: colors.primaryDark, fontFamily: fonts.medium, fontSize: 12, marginTop: 12 }, delete: { alignItems: "center", padding: 15, marginTop: 16 }, deleteText: { color: colors.danger, fontFamily: fonts.semibold, fontWeight: '600', fontSize: 12 } });
