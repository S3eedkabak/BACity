import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { AnimatedPressable } from './motion/Motion';
import { SaveEventAction } from './interactions/SaveEventAction';
import { AppIcon } from './AppIcon';
import { EventMedia } from './EventMedia';
import { EventMetadata } from './EventMetadata';
import { eventPresentations, type EventPresentation, type EventCardVariant } from './eventPresentation';
import { OverflowMenu, ListItem } from './SocialUI';
import { eventCoordinates } from '../map/eventLocation';
import { useViewOnMap } from '../map/eventTarget';
import { availabilityLabel } from '../map/eventAvailability';
import { useEventNavigation } from '../hooks/useEventNavigation';
import { colors } from '../theme/colors';
import { tokens } from '../theme/tokens';
import { themedStyles, useThemeRevision } from '../theme/appearance';
import { EventOut } from '../types/event';
export type { EventCardVariant } from './eventPresentation';
export function EventCard({ event, explanation, variant = 'feed', presentation }: { event: EventOut; explanation?: string; variant?: EventCardVariant; presentation?: EventPresentation }) {
  useThemeRevision(); const openEvent = useEventNavigation(); const viewOnMap = useViewOnMap(); const [menu, setMenu] = useState(false);
  const layout = presentation ?? eventPresentations[variant];
  const photoLed = layout === 'editorial';
  const feature = photoLed || ((layout === 'feature' || layout === 'rail') && !!event.image_url);
  return <View style={[styles.wrap, layout === 'rail' && styles.rail, feature && styles.feature]}>
    <View style={{ flexDirection: 'row', alignItems: 'flex-start' }}>
      <AnimatedPressable accessibilityRole="button" accessibilityLabel={`Open ${event.title}`} onPress={() => openEvent(event.id)} onLongPress={() => setMenu(true)} style={[styles.card, feature && { flexDirection: 'column' }]}>
        <EventMedia uri={event.image_url} category={event.category} style={photoLed ? styles.homeImage : feature ? styles.featureImage : styles.image} />
        <View style={[styles.body, feature && { padding: photoLed ? 18 : 12 }]}>
          <Text style={styles.when}>{availabilityLabel(event)}</Text>
          <Text style={[styles.title, photoLed && styles.homeTitle]} numberOfLines={3}>{event.title}</Text>
          <Text style={styles.location} numberOfLines={2}>{event.venue?.name || event.address || 'Bratislava'}</Text>
          <EventMetadata event={event} />
          {!!explanation && <Text style={styles.reason} numberOfLines={1}>{explanation}</Text>}
        </View>
      </AnimatedPressable>
      <View style={[styles.actions, feature && { position: 'absolute', top: 4, right: 4, borderRadius: 24, backgroundColor: colors.surface }]}>
        <SaveEventAction event={event} />
        <AnimatedPressable accessibilityRole="button" accessibilityLabel={`More actions for ${event.title}`} onPress={() => setMenu(true)} style={styles.more}><AppIcon name="ellipsis-horizontal" color={colors.textMuted} size={20} /></AnimatedPressable>
      </View>
    </View>
    <OverflowMenu visible={menu} title={event.title} onClose={() => setMenu(false)}>
      <ListItem icon="calendar-outline" title="Event details" onPress={() => { setMenu(false); openEvent(event.id); }} />
      {eventCoordinates(event) && <ListItem icon="map-outline" title={`View ${event.title} on Map`} onPress={() => { setMenu(false); viewOnMap(event); }} />}
    </OverflowMenu>
  </View>;
}
const styles = themedStyles(() => ({
  wrap: { paddingVertical: tokens.space.control, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  rail: { width: 280, marginRight: tokens.space.md },
  feature: { borderBottomWidth: 0, backgroundColor: colors.surface, borderRadius: tokens.radius.card, overflow: 'hidden', paddingVertical: 0, marginBottom: tokens.space.sm },
  card: { flex: 1, flexDirection: 'row', gap: tokens.space.md, minWidth: 0 },
  image: { width: tokens.layout.compactImageWidth, height: tokens.layout.compactImageHeight, borderRadius: tokens.radius.sm }, featureImage: { width: '100%', height: 168 },
  homeImage: { width: '100%', aspectRatio: tokens.image.feed }, homeTitle: { ...tokens.type.section },
  body: { flex: 1, gap: tokens.space.xs, minWidth: 0 }, title: { ...tokens.type.eventTitle, color: colors.text },
  when: { ...tokens.type.caption, color: colors.primaryDark }, location: { ...tokens.type.metadata, color: colors.textMuted }, meta: { ...tokens.type.caption, color: colors.textMuted }, reason: { ...tokens.type.caption, color: colors.primaryDark },
  actions: { width: 48, alignItems: 'center', gap: 4 }, more: { width: 48, height: 48, alignItems: 'center', justifyContent: 'center' },
}));
