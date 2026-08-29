/**
 * Event detail (spec sections 6, 53): full description, venue/location,
 * source attribution link back to the original page, and a save toggle.
 */
import { useLayoutEffect } from "react";
import { Linking, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams, useNavigation } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useEvent, useSavedEvents, useToggleSaveEvent } from "../../src/hooks/useEvents";
import { useAuthStore } from "../../src/store/authStore";
import { LoadingState } from "../../src/components/LoadingState";
import { EmptyState } from "../../src/components/EmptyState";
import { colors } from "../../src/theme/colors";

function formatWhen(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit",
  });
}

export default function EventDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const navigation = useNavigation();
  const token = useAuthStore((s) => s.token);
  const { data: event, isLoading, isError } = useEvent(id);
  const { data: savedEvents } = useSavedEvents();
  const toggleSave = useToggleSaveEvent();

  const isSaved = !!savedEvents?.some((e) => e.id === id);

  useLayoutEffect(() => {
    navigation.setOptions({ title: event?.title ?? "Event" });
  }, [navigation, event]);

  if (isLoading) return <LoadingState />;
  if (isError || !event) return <EmptyState title="Event not found" />;

  const priceLabel =
    event.price === null ? "Price unknown" : event.price === 0 ? "Free" : `${event.price} ${event.currency ?? "EUR"}`;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.category}>{event.category.toUpperCase()}</Text>
      <Text style={styles.title}>{event.title}</Text>
      <Text style={styles.when}>{formatWhen(event.start_time)}</Text>

      <View style={styles.row}>
        <Ionicons name="location-outline" size={16} color={colors.textMuted} />
        <Text style={styles.rowText}>
          {event.venue?.name ?? event.address ?? "Location unknown"}
        </Text>
      </View>
      <View style={styles.row}>
        <Ionicons name="pricetag-outline" size={16} color={colors.textMuted} />
        <Text style={styles.rowText}>{priceLabel}</Text>
      </View>

      {event.description && <Text style={styles.description}>{event.description}</Text>}

      {token && (
        <Pressable
          style={[styles.saveButton, isSaved && styles.saveButtonActive]}
          onPress={() => toggleSave.mutate({ id: event.id, saved: isSaved })}
          disabled={toggleSave.isPending}
        >
          <Ionicons name={isSaved ? "bookmark" : "bookmark-outline"} size={18} color="#fff" />
          <Text style={styles.saveButtonText}>{isSaved ? "Saved" : "Save event"}</Text>
        </Pressable>
      )}

      <Pressable style={styles.sourceLink} onPress={() => Linking.openURL(event.source_url)}>
        <Text style={styles.sourceLinkText}>View original event ↗</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: 20, paddingBottom: 48 },
  category: { color: colors.accent, fontSize: 12, fontWeight: "700", letterSpacing: 0.5, marginBottom: 6 },
  title: { color: colors.text, fontSize: 24, fontWeight: "800", marginBottom: 10 },
  when: { color: colors.textMuted, fontSize: 15, marginBottom: 16 },
  row: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 8 },
  rowText: { color: colors.text, fontSize: 14 },
  description: { color: colors.text, fontSize: 15, lineHeight: 22, marginTop: 16 },
  saveButton: {
    flexDirection: "row",
    gap: 8,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.primaryMuted,
    borderRadius: 10,
    padding: 14,
    marginTop: 24,
  },
  saveButtonActive: { backgroundColor: colors.primary },
  saveButtonText: { color: "#fff", fontWeight: "700" },
  sourceLink: { marginTop: 16, alignItems: "center" },
  sourceLinkText: { color: colors.accent, fontSize: 13 },
});