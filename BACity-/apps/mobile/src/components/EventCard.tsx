import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { AnimatedPressable } from './motion/Motion';
import { SaveEventAction } from './interactions/SaveEventAction';
import { AppIcon } from './AppIcon';
import { EventMedia } from './EventMedia';
import { OverflowMenu, ListItem } from './SocialUI';
import { eventCoordinates } from '../map/eventLocation';
import { useViewOnMap } from '../map/eventTarget';
import { availabilityLabel } from '../map/eventAvailability';
import { useEventNavigation } from '../hooks/useEventNavigation';
import { colors } from '../theme/colors';
import { tokens } from '../theme/tokens';
import { themedStyles, useThemeRevision } from '../theme/appearance';
import { EventOut } from '../types/event';
export type EventCardVariant = 'home' | 'hero' | 'feed' | 'horizontal' | 'compact' | 'map' | 'saved' | 'planner' | 'premium' | 'organizer';
export function EventCard({ event, explanation, variant = 'feed' }: { event: EventOut; explanation?: string; variant?: EventCardVariant; entranceDelay?: number }) {
  useThemeRevision(); const openEvent = useEventNavigation(); const viewOnMap = useViewOnMap(); const [menu, setMenu] = useState(false);
  const photoLed = variant === 'home';
  const feature = photoLed || ((variant === 'hero' || variant === 'horizontal') && !!event.image_url);
  const price = event.price === 0 ? 'Free' : event.price == null ? 'Price unknown' : `${event.price} ${event.currency || 'EUR'}`;
  return <View style={[styles.wrap, variant === 'horizontal' && { width: 280, marginRight: 12 }, feature && styles.feature]}>
    <View style={{ flexDirection: 'row', alignItems: 'flex-start' }}>
      <AnimatedPressable accessibilityRole="button" accessibilityLabel={`Open ${event.title}`} onPress={() => openEvent(event.id)} onLongPress={() => setMenu(true)} style={[styles.card, feature && { flexDirection: 'column' }]}>
        <EventMedia uri={event.image_url} category={event.category} style={photoLed ? styles.homeImage : feature ? styles.featureImage : styles.image} />
        <View style={[styles.body, feature && { padding: photoLed ? 18 : 12 }]}>
          <Text style={styles.when}>{availabilityLabel(event)}</Text>
          <Text style={[styles.title, photoLed && styles.homeTitle]} numberOfLines={3}>{event.title}</Text>
          <Text style={styles.location} numberOfLines={2}>{event.venue?.name || event.address || 'Bratislava'}</Text>
          <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}><Text style={styles.meta}>{event.category}</Text><Text style={[styles.meta, { color: event.price === 0 ? colors.free : colors.textMuted }]}>{price}</Text></View>
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
  wrap: { paddingVertical: 12, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  feature: { borderBottomWidth: 0, backgroundColor: colors.surface, borderRadius: 16, overflow: 'hidden', paddingVertical: 0, marginBottom: 8 },
  card: { flex: 1, flexDirection: 'row', gap: 12, minWidth: 0 },
  image: { width: 88, height: 104, borderRadius: 12 }, featureImage: { width: '100%', height: 168 },
  homeImage: { width: '100%', aspectRatio: tokens.image.feed }, homeTitle: { fontSize: 22, lineHeight: 27, fontWeight: '700' },
  body: { flex: 1, gap: 4, minWidth: 0 }, title: { fontSize: 17, lineHeight: 23, fontWeight: '600', color: colors.text, letterSpacing: -.3 },
  when: { ...tokens.type.caption, color: colors.primaryDark }, location: { ...tokens.type.metadata, color: colors.textMuted }, meta: { ...tokens.type.caption, color: colors.textMuted }, reason: { ...tokens.type.caption, color: colors.primaryDark },
  actions: { width: 48, alignItems: 'center', gap: 4 }, more: { width: 48, height: 48, alignItems: 'center', justifyContent: 'center' },
}));
