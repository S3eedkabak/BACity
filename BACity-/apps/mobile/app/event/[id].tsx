import { Button } from "../../src/components/CommunityUI";
import { EventMedia } from '../../src/components/EventMedia';
import { MediaScrim } from '../../src/components/MediaScrim';
import { Discussion } from "../../src/components/Discussion";
import { Pressable, ScrollView, Share, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from 'react-native-safe-area-context';
import { useState } from 'react';
import { IconButton, ListItem, OverflowMenu } from '../../src/components/SocialUI';
import { externalLinking as Linking } from "../../src/api/externalLinking";
import { router, useLocalSearchParams } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useEvent, useSavedEvents, useToggleSaveEvent } from "../../src/hooks/useEvents";
import { useAuthStore } from "../../src/store/authStore";
import { LoadingState } from "../../src/components/LoadingState";
import { EmptyState } from "../../src/components/EmptyState";
import { colors } from "../../src/theme/colors";
import { fonts } from "../../src/theme/fonts";
import { PlusGateAction } from "../../src/plus/usePlusGate";
import { eventChainsRoute } from "../../src/eventChains/presentation";

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
  const [menu, setMenu] = useState(false);
  const { id } = useLocalSearchParams<{ id: string }>();
  const token = useAuthStore((s) => s.token);
  const { data: event, isLoading, isError } = useEvent(id);
  const { data: savedEvents } = useSavedEvents();
  const toggleSave = useToggleSaveEvent();
  const isSaved = !!savedEvents?.some((e) => e.id === id);

  if (isLoading) return <LoadingState />;
  if (isError || !event) return <EmptyState title="Event not found" />;

  const price =
    event.price === 0
      ? "Free"
      : event.price == null
      ? "Price unknown"
      : event.price + " " + (event.currency ?? "EUR");

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      <View style={styles.hero}>
        <EventMedia uri={event.image_url} category={event.category} style={styles.heroImage} />
        <MediaScrim />
        <View style={styles.heroTop}>
          <Pressable accessibilityRole="button" accessibilityLabel="Go back" style={styles.backButton} onPress={() => router.canGoBack() ? router.back() : router.replace('/(tabs)/discover')}>
            <Ionicons name="chevron-back" size={20} color={colors.text} />
          </Pressable>
          <View style={styles.heroBadges}>
          <View style={styles.categoryPill}>
            <Text style={styles.category}>{event.category}</Text>
          </View>
          <View style={styles.backButton}><IconButton icon="ellipsis-horizontal" label="Event actions" onPress={() => setMenu(true)} /></View>
          {event.price === 0 && (
            <View style={styles.freePill}>
              <Text style={styles.freeText}>FREE</Text>
            </View>
          )}
          </View>
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

      <PlusGateAction feature="event_chains" onAllowed={() => router.push(eventChainsRoute(event.id))}>
        {({ onPress, loading }) => <Pressable
          accessibilityRole="button"
          accessibilityLabel="Build around this event"
          style={({ pressed }) => [styles.chainButton, pressed && styles.chainPressed, loading && styles.chainDisabled]}
          onPress={onPress}
          disabled={loading}
        >
          <View style={styles.chainIcon}><Ionicons name="git-branch-outline" size={20} color={colors.white} /></View>
          <View style={styles.chainCopy}>
            <Text style={styles.chainTitle}>Build around this event</Text>
            <Text style={styles.chainSubtitle}>Find compatible events before or after</Text>
          </View>
          {loading ? <Ionicons name="ellipsis-horizontal" size={18} color={colors.primaryDark} /> : <Ionicons name="chevron-forward" size={18} color={colors.text} />}
        </Pressable>}
      </PlusGateAction>

      {!!event.source_url && <Pressable style={styles.sourceButton} onPress={() => Linking.openURL(event.source_url)}>
        <Text style={styles.sourceText}>View original event</Text>
        <Ionicons name="arrow-up-outline" size={16} color={colors.primaryDark} />
      </Pressable>}
      {event.venue && <Button title={"More at " + event.venue.name} onPress={() => router.push(`/venue/${event.venue!.id}`)} />}
      <Discussion id={id} kind="event" />
    </ScrollView>
    <OverflowMenu visible={menu} title="Event actions" onClose={() => setMenu(false)}>
      <ListItem icon="share-outline" title="Share event" onPress={() => { setMenu(false); void Share.share({ title: event.title, message: event.title + (event.source_url ? '\n' + event.source_url : '') }); }} />
      <ListItem icon="albums-outline" title="Add to a collection" onPress={() => { setMenu(false); router.push({ pathname: '/collection', params: { type: 'event', id } }); }} />
      <ListItem icon="create-outline" title="Suggest a correction" onPress={() => { setMenu(false); router.push({ pathname: '/correction', params: { type: 'event', id } }); }} />
    </OverflowMenu>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { width: '100%', maxWidth: 760, alignSelf: 'center', paddingBottom: 45 },
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
    alignItems: "flex-start",
  },
  backButton: {
    width: 42,
    height: 42,
    borderRadius: 16,
    backgroundColor: "rgba(255,255,255,0.94)",
    alignItems: "center",
    justifyContent: "center",
  },
  heroBadges: {
    flexDirection: "row",
    gap: 7,
    alignItems: "center",
  },
  categoryPill: {
    backgroundColor: "rgba(39,35,41,0.78)",
    paddingHorizontal: 11,
    paddingVertical: 7,
    borderRadius: 99,
  },
  category: { color: colors.white, fontFamily: fonts.semibold, fontWeight: '600', fontSize: 12 },
  freePill: {
    backgroundColor: colors.white,
    paddingHorizontal: 11,
    paddingVertical: 7,
    borderRadius: 99,
  },
  freeText: { color: colors.free, fontFamily: fonts.black, fontWeight: '800', fontSize: 12 },
  heroText: { position: "absolute", left: 18, right: 18, bottom: 20 },
  title: {
    color: colors.white,
    fontFamily: fonts.black, fontWeight: '800',
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
  label: { color: colors.textMuted, fontFamily: fonts.semibold, fontWeight: '600', fontSize: 12, letterSpacing: 1 },
  value: { color: colors.text, fontFamily: fonts.semibold, fontWeight: '600', fontSize: 12, lineHeight: 18, marginTop: 4 },
  section: { paddingHorizontal: 18, paddingTop: 22 },
  sectionTitle: { color: colors.text, fontFamily: fonts.black, fontWeight: '800', fontSize: 19 },
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
  saveText: { color: colors.text, fontFamily: fonts.semibold, fontWeight: '600', fontSize: 12 },
  savedText: { color: colors.white },
  chainButton: { minHeight: 72, marginHorizontal: 18, marginTop: 10, paddingHorizontal: 13, borderRadius: 20, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, flexDirection: "row", alignItems: "center", gap: 11 },
  chainPressed: { opacity: .7 }, chainDisabled: { opacity: .62 }, chainIcon: { width: 42, height: 42, borderRadius: 15, backgroundColor: colors.primary, alignItems: "center", justifyContent: "center" },
  chainCopy: { flex: 1 }, chainTitle: { color: colors.text, fontFamily: fonts.black, fontWeight: '800', fontSize: 13 }, chainSubtitle: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 12, marginTop: 3 },
  sourceButton: {
    alignSelf: "center",
    flexDirection: "row",
    gap: 7,
    alignItems: "center",
    padding: 10,
  },
  sourceText: { color: colors.primaryDark, fontFamily: fonts.semibold, fontWeight: '600', fontSize: 12 },
});
