import { useLayoutEffect } from "react";
import { Image, Linking, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams, useNavigation } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useEvent, useSavedEvents, useToggleSaveEvent } from "../../src/hooks/useEvents";
import { useAuthStore } from "../../src/store/authStore";
import { LoadingState } from "../../src/components/LoadingState";
import { EmptyState } from "../../src/components/EmptyState";
import { colors } from "../../src/theme/colors";

function formatWhen(iso: string) {
  return new Date(iso).toLocaleString(undefined, { weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });
}

export default function EventDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const navigation = useNavigation();
  const token = useAuthStore((s) => s.token);
  const { data: event, isLoading, isError } = useEvent(id);
  const { data: savedEvents } = useSavedEvents();
  const toggleSave = useToggleSaveEvent();
  const isSaved = !!savedEvents?.some((e) => e.id === id);

  useLayoutEffect(() => { navigation.setOptions({ title: "" }); }, [navigation]);

  if (isLoading) return <LoadingState />;
  if (isError || !event) return <EmptyState title="Event not found" />;

  const price = event.price === 0 ? "Free" : event.price == null ? "Price unknown" : `${event.price} ${event.currency ?? "EUR"}`;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
      <View style={styles.hero}>
        {event.image_url ? <Image source={{ uri: event.image_url }} style={styles.heroImage} resizeMode="cover" /> : <View style={styles.fallback}><Ionicons name="sparkles" size={50} color={colors.accent} /></View>}
        <View style={styles.heroShade} />
        <View style={styles.heroText}><Text style={styles.category}>{event.category.toUpperCase()}</Text><Text style={styles.title}>{event.title}</Text></View>
      </View>

      <View style={styles.infoCard}>
        <View style={styles.infoRow}><View style={styles.infoIcon}><Ionicons name="calendar-outline" size={18} color={colors.accent} /></View><View style={styles.infoCopy}><Text style={styles.label}>WHEN</Text><Text style={styles.value}>{formatWhen(event.start_time)}</Text></View></View>
        <View style={styles.infoRow}><View style={styles.infoIcon}><Ionicons name="location-outline" size={18} color={colors.accent} /></View><View style={styles.infoCopy}><Text style={styles.label}>WHERE</Text><Text style={styles.value}>{event.venue?.name ?? event.address ?? "Bratislava"}</Text></View></View>
        <View style={styles.infoRow}><View style={styles.infoIcon}><Ionicons name="pricetag-outline" size={18} color={colors.accent} /></View><View style={styles.infoCopy}><Text style={styles.label}>PRICE</Text><Text style={styles.value}>{price}</Text></View></View>
      </View>

      {event.description && <View style={styles.section}><Text style={styles.sectionTitle}>About this event</Text><Text style={styles.description}>{event.description}</Text></View>}

      {token && <Pressable style={[styles.saveButton, isSaved && styles.saved]} onPress={() => toggleSave.mutate({ id: event.id, saved: isSaved })} disabled={toggleSave.isPending}>
        <Ionicons name={isSaved ? "bookmark" : "bookmark-outline"} size={20} color={colors.background} /><Text style={styles.saveText}>{isSaved ? "Saved to your plans" : "Save this event"}</Text>
      </Pressable>}

      <Pressable style={styles.sourceButton} onPress={() => Linking.openURL(event.source_url)}>
        <Text style={styles.sourceText}>View original event</Text><Ionicons name="open-outline" size={16} color={colors.accent} />
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { paddingBottom: 45 },
  hero: { height: 410, marginHorizontal: 14, borderRadius: 28, overflow: "hidden", backgroundColor: colors.surface },
  heroImage: { width: "100%", height: "100%" },
  fallback: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: "#24213F" },
  heroShade: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(0,0,0,0.34)" },
  heroText: { position: "absolute", left: 20, right: 20, bottom: 22 },
  category: { color: colors.accent, fontSize: 10, fontWeight: "900", letterSpacing: 1.3, marginBottom: 7 },
  title: { color: colors.white, fontSize: 30, lineHeight: 34, fontWeight: "900", letterSpacing: -0.7 },
  infoCard: { margin: 14, marginBottom: 4, padding: 17, borderRadius: 22, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, gap: 17 },
  infoRow: { flexDirection: "row", alignItems: "center", gap: 12 },
  infoIcon: { width: 42, height: 42, borderRadius: 14, backgroundColor: colors.surfaceAlt, alignItems: "center", justifyContent: "center" },
  infoCopy: { flex: 1 },
  label: { color: colors.textMuted, fontSize: 9, fontWeight: "900", letterSpacing: 1 },
  value: { color: colors.text, fontSize: 13, fontWeight: "700", marginTop: 3 },
  section: { paddingHorizontal: 18, paddingTop: 20 },
  sectionTitle: { color: colors.text, fontSize: 19, fontWeight: "900" },
  description: { color: colors.textMuted, fontSize: 14, lineHeight: 22, marginTop: 8 },
  saveButton: { margin: 18, marginBottom: 8, height: 54, borderRadius: 18, backgroundColor: colors.accent, alignItems: "center", justifyContent: "center", flexDirection: "row", gap: 8 },
  saved: { backgroundColor: colors.text },
  saveText: { color: colors.background, fontSize: 13, fontWeight: "900" },
  sourceButton: { alignSelf: "center", flexDirection: "row", gap: 7, alignItems: "center", padding: 10 },
  sourceText: { color: colors.accent, fontSize: 12, fontWeight: "800" },
});