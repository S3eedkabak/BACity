import { Text, View, StyleSheet } from "react-native";
import { AnimatedPressable as Pressable } from "./motion/Motion";
import { EventCard } from "./EventCard";
import { eventPriceLabel } from "./EventMetadata";
import { SaveEventAction } from "./interactions/SaveEventAction";
import { EventMedia } from "./EventMedia";
import { MediaScrim } from "./MediaScrim";
import { IconButton } from "./SocialUI";
import { AppIcon } from "./AppIcon";
import { availabilityLabel } from "../map/eventAvailability";
import { eventCoordinates } from "../map/eventLocation";
import { useViewOnMap } from "../map/eventTarget";
import { useEventNavigation } from "../hooks/useEventNavigation";
import { themedStyles, useThemeRevision } from "../theme/appearance";
import { colors } from "../theme/colors";
import { fontStyles } from "../theme/fonts";
import { tokens } from "../theme/tokens";
import type { EventOut } from "../types/event";

function dateParts(iso: string) {
  const date = new Date(iso);
  return {
    day: date
      .toLocaleDateString(undefined, {
        timeZone: "Europe/Bratislava",
        weekday: "short",
      })
      .toUpperCase(),
    date: date.toLocaleDateString(undefined, {
      timeZone: "Europe/Bratislava",
      day: "numeric",
      month: "short",
    }),
    time: date.toLocaleTimeString(undefined, {
      timeZone: "Europe/Bratislava",
      hour: "2-digit",
      minute: "2-digit",
    }),
  };
}

export function FeaturedEvent({ event }: { event: EventOut }) {
  useThemeRevision();
  const openEvent = useEventNavigation();
  const date = dateParts(event.next_occurrence_start ?? event.start_time);
  const viewOnMap = useViewOnMap();
  if (!event.image_url) return <EventCard event={event} presentation="row" />;
  return (
    <View>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={"Open " + event.title}
        onPress={() => openEvent(event.id)}
        style={({ pressed }) => [
          styles.featured,
          pressed && styles.pressed,
        ]}
      >
        <EventMedia
          uri={event.image_url}
          category={event.category}
          style={styles.featuredImage}
        />
        <MediaScrim />
        <View style={styles.featuredTop}>
          <View style={styles.dateBadge}>
            <Text maxFontSizeMultiplier={tokens.accessibility.navigationLabelMaxScale} style={styles.dateDay}>{date.day}</Text>
            <Text maxFontSizeMultiplier={tokens.accessibility.navigationLabelMaxScale} style={styles.dateDate}>{date.date}</Text>
          </View>
          <View style={[styles.priceBadge, { marginRight: 104 }]}>
            <Text maxFontSizeMultiplier={tokens.accessibility.navigationLabelMaxScale} style={styles.priceText}>{eventPriceLabel(event)}</Text>
          </View>
        </View>
        <View style={styles.featuredBottom}>
          <View style={styles.categoryBadge}>
            <Text style={styles.categoryText}>{event.category}</Text>
          </View>
          <Text style={styles.metaText}>{availabilityLabel(event)}</Text>
          <Text style={styles.featuredTitle} numberOfLines={2}>
            {event.title}
          </Text>
          <View style={styles.metaRow}>
            <AppIcon name="location-outline" size={15} color={colors.onMedia} />
            <Text style={styles.metaText} numberOfLines={1}>
              {event.venue?.name ?? event.address ?? "Bratislava"}
            </Text>
          </View>
        </View>
      </Pressable>
      <View
        style={{
          position: "absolute",
          top: 14,
          right: 14,
          backgroundColor: colors.mediaOverlay,
          borderRadius: 24,
        }}
      >
        <SaveEventAction event={event} />
      </View>
      {eventCoordinates(event) && (
        <View
          style={{
            position: "absolute",
            top: 68,
            right: 14,
            backgroundColor: colors.mediaOverlay,
            borderRadius: 24,
          }}
        >
          <IconButton
            icon="map-outline"
            label={`View ${event.title} on Map`}
            onPress={() => viewOnMap(event)}
          />
        </View>
      )}
    </View>
  );
}

const styles = themedStyles(() => ({
  featured: {
    minHeight: tokens.layout.featureHeight,
    borderRadius: tokens.radius.card,
    overflow: "hidden",
    backgroundColor: colors.primarySoft,
    shadowColor: colors.shadow,
    shadowOpacity: 0,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 9 },
    elevation: tokens.elevation.flat,
  },
  featuredImage: { ...StyleSheet.absoluteFillObject },
  featuredTop: {
    position: "absolute",
    left: 14,
    right: 14,
    top: 14,
    flexDirection: "row",
    justifyContent: "space-between",
  },
  dateBadge: {
    backgroundColor: colors.mediaOverlay,
    borderRadius: tokens.radius.sm,
    paddingHorizontal: 11,
    paddingVertical: 9,
    alignItems: "center",
  },
  dateDay: {
    color: colors.primaryDark,
    ...fontStyles.black,
    fontWeight: "800",
    fontSize: 12,
    letterSpacing: 0.7,
  },
  dateDate: {
    color: colors.text,
    ...fontStyles.black,
    fontWeight: "800",
    fontSize: 12,
    marginTop: 2,
  },
  priceBadge: {
    alignSelf: "flex-start",
    backgroundColor: colors.overlay,
    borderRadius: tokens.radius.pill,
    paddingHorizontal: 11,
    paddingVertical: 8,
  },
  priceText: {
    color: colors.onMedia,
    ...fontStyles.semibold,
    fontWeight: "600",
    fontSize: 12,
  },
  featuredBottom: { paddingHorizontal: tokens.space.control, paddingTop: 124, paddingBottom: tokens.space.control },
  categoryBadge: {
    alignSelf: "flex-start",
    backgroundColor: colors.primary,
    borderRadius: tokens.radius.pill,
    paddingHorizontal: 10,
    paddingVertical: 6,
    marginBottom: 8,
  },
  categoryText: {
    color: colors.onMedia,
    ...fontStyles.black,
    fontWeight: "800",
    fontSize: 12,
  },
  featuredTitle: {
    color: colors.onMedia,
    ...tokens.type.featureTitle,
  },
  metaRow: { flexDirection: "row", alignItems: "center", gap: 5, marginTop: 9 },
  metaText: {
    color: colors.mediaMuted,
    ...fontStyles.medium,
    fontSize: 12,
    maxWidth: 190,
  },
  metaDot: {
    width: 3,
    height: 3,
    borderRadius: 2,
    backgroundColor: colors.mediaMuted,
    marginHorizontal: 3,
  },
  pressed: { opacity: tokens.opacity.pressed },
}));
