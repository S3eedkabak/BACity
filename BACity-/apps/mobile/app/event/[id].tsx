import { Discussion } from "../../src/components/Discussion";
import { useLayoutEffect } from "react";
import { Image, Linking, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams, useNavigation } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useEvent, useSavedEvents, useToggleSaveEvent } from "../../src/hooks/useEvents";
import { useAuthStore } from "../../src/store/authStore";
import { LoadingState } from "../../src/components/LoadingState";
import { EmptyState } from "../../src/components/EmptyState";
import { imageForCategory } from "../../src/theme/categoryImages";
import { colors } from "../../src/theme/colors";
import { fonts } from "../../src/theme/fonts";

function formatWhen(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "long",
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
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
    navigation.setOptions({ title: "" });
  }, [navigation]);

  if (isLoading) return <LoadingState />;
  if (isError || !event) return <EmptyState title="Event not found" />;

  const price =
    event.price === 0
      ? "Free"
      : event.price == null
      ? "Price unknown"
      : event.price + " " + (event.currency ?? "EUR");

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      <View style={styles.hero}>
        <Image
          source={{ uri: event.image_url || imageForCategory(event.category) }}
          style={styles.heroImage}
          resizeMode="cover"
        />
        <View style={styles.heroShade} />
        <View style={styles.heroTop}>
          <View style={styles.categoryPill}>
            <Text style={styles.category}>{event.category}</Text>
          </View>
          {event.price === 0 && (
            <View style={styles.freePill}>
              <Text style={styles.freeText}>FREE</Text>
            </View>
          )}
        </View>
        <View style={styles.heroText}>
          <Text style={styles.title}>{event.title}</Text>
          <View style={styles.locationLine}>
            <Ionicons name="location-outline" size={15} color={colors.white} />
            <Text style={styles.location}>
              {event.venue?.name ?? event.address ?? "Bratislava"}
            </Text>
          </View>
        </View>
      </View>

      <View style={styles.infoGrid}>
        <View style={styles.infoCard}>
          <View style={styles.infoIcon}>
            <Ionicons name="calendar-outline" size={18} color={colors.primary} />
          </View>
          <Text style={styles.label}>WHEN</Text>
          <Text style={styles.value}>{formatWhen(event.start_time)}</Text>
        </View>

        <View style={styles.infoCard}>
          <View style={styles.infoIcon}>
            <Ionicons name="pricetag-outline" size={18} color={colors.primary} />
          </View>
          <Text style={styles.label}>PRICE</Text>
          <Text style={styles.value}>{price}</Text>
        </View>
      </View>

      {event.description && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>About this event</Text>
          <Text style={styles.description}>{event.description}</Text>
        </View>
      )}

      {token && (
        <Pressable
          style={[styles.saveButton, isSaved && styles.saved]}
          onPress={() => toggleSave.mutate({ id: event.id, saved: isSaved })}
          disabled={toggleSave.isPending}
        >
          <Ionicons
            name={isSaved ? "heart" : "heart-outline"}
            size={19}
            color={isSaved ? colors.white : colors.text}
          />
          <Text style={[styles.saveText, isSaved && styles.savedText]}>
            {isSaved ? "Saved to your plans" : "Save this event"}
          </Text>
        </Pressable>
      )}

      <Pressable style={styles.sourceButton} onPress={() => Linking.openURL(event.source_url)}>
        <Text style={styles.sourceText}>View original event</Text>
        <Ionicons name="arrow-up-outline" size={16} color={colors.primaryDark} />
      </Pressable>
      <Discussion id={id} kind="event" />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { paddingBottom: 45 },
  hero: {
    height: 405,
    marginHorizontal: 14,
    borderRadius: 28,
    overflow: "hidden",
    backgroundColor: colors.primarySoft,
  },
  heroImage: { width: "100%", height: "100%" },
  heroShade: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(32,23,28,0.28)" },
  heroTop: {
    position: "absolute",
    top: 16,
    left: 16,
    right: 16,
    flexDirection: "row",
    justifyContent: "space-between",
  },
  categoryPill: {
    backgroundColor: "rgba(39,35,41,0.78)",
    paddingHorizontal: 11,
    paddingVertical: 7,
    borderRadius: 99,
  },
  category: { color: colors.white, fontFamily: fonts.semibold, fontSize: 10 },
  freePill: {
    backgroundColor: colors.white,
    paddingHorizontal: 11,
    paddingVertical: 7,
    borderRadius: 99,
  },
  freeText: { color: colors.free, fontFamily: fonts.black, fontSize: 9 },
  heroText: { position: "absolute", left: 18, right: 18, bottom: 20 },
  title: {
    color: colors.white,
    fontFamily: fonts.black,
    fontSize: 30,
    lineHeight: 33,
    letterSpacing: -0.8,
  },
  locationLine: { flexDirection: "row", alignItems: "center", gap: 5, marginTop: 8 },
  location: { color: colors.white, fontFamily: fonts.medium, fontSize: 12, flex: 1 },
  infoGrid: {
    flexDirection: "row",
    gap: 10,
    paddingHorizontal: 14,
    marginTop: 12,
  },
  infoCard: {
    flex: 1,
    padding: 14,
    borderRadius: 20,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  infoIcon: {
    width: 38,
    height: 38,
    borderRadius: 13,
    backgroundColor: colors.primarySoft,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 10,
  },
  label: { color: colors.textMuted, fontFamily: fonts.semibold, fontSize: 8, letterSpacing: 1 },
  value: { color: colors.text, fontFamily: fonts.semibold, fontSize: 12, lineHeight: 17, marginTop: 4 },
  section: { paddingHorizontal: 18, paddingTop: 22 },
  sectionTitle: { color: colors.text, fontFamily: fonts.black, fontSize: 19 },
  description: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 13, lineHeight: 21, marginTop: 8 },
  saveButton: {
    margin: 18,
    marginBottom: 8,
    height: 54,
    borderRadius: 18,
    backgroundColor: colors.primarySoft,
    borderWidth: 1,
    borderColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: 8,
  },
  saved: { backgroundColor: colors.primary, borderColor: colors.primary },
  saveText: { color: colors.text, fontFamily: fonts.semibold, fontSize: 12 },
  savedText: { color: colors.white },
  sourceButton: {
    alignSelf: "center",
    flexDirection: "row",
    gap: 7,
    alignItems: "center",
    padding: 10,
  },
  sourceText: { color: colors.primaryDark, fontFamily: fonts.semibold, fontSize: 11 },
});
