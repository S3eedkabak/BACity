import { eventCoordinates } from '../map/eventLocation';
import { useViewOnMap } from '../map/eventTarget';
import { availabilityLabel } from '../map/eventAvailability';
import { AppIcon } from "./AppIcon";
import { Platform, StyleSheet, Text, View } from 'react-native';
import { AnimatedPressable as Pressable } from './motion/Motion';
import { EventOut } from '../types/event';
import { colors } from '../theme/colors';
import { tokens } from '../theme/tokens';
import { EventMedia } from './EventMedia';
import { useState } from 'react';
import { Reveal } from './motion/Motion';
import { useEventNavigation } from '../hooks/useEventNavigation';

export type EventCardVariant = 'hero' | 'feed' | 'horizontal' | 'compact' | 'map' | 'saved' | 'planner' | 'premium' | 'organizer';
export function EventCard({ event, explanation, saved, saving = false, onToggleSave, variant = 'feed', entranceDelay }: {
  event: EventOut; explanation?: string; saved?: boolean; saving?: boolean; onToggleSave?: () => void; variant?: EventCardVariant; entranceDelay?: number;
}) {
  const [initialDelay] = useState(entranceDelay);
  const openEvent = useEventNavigation();
  const viewOnMap = useViewOnMap();
  const compact = ['compact', 'map', 'planner'].includes(variant);
  const premium = variant === 'premium';
  const card = <Pressable accessibilityRole="button" accessibilityLabel={`Open ${event.title}`} onPress={() => openEvent(event.id)}
    style={({ pressed }) => [styles.card, compact && styles.compact, variant === 'horizontal' && styles.rail, premium && styles.premium, pressed && styles.pressed]}>
    <View style={[styles.mediaWrap, variant === 'hero' && styles.heroMedia, variant === 'horizontal' && styles.railMedia, variant === 'saved' && styles.savedMedia, variant === 'organizer' && styles.organizerMedia, compact && styles.compactMedia]}>
      <EventMedia uri={event.image_url} category={event.category} style={StyleSheet.absoluteFill} />
      {!compact && <View style={styles.mediaMeta}><Text style={styles.tag}>{event.category}</Text><Text style={styles.tag}>{event.price === 0 ? 'Free' : event.price == null ? 'Price unknown' : `${event.price} ${event.currency || 'EUR'}`}</Text></View>}
      {onToggleSave && Platform.OS !== 'web' && <Pressable accessibilityRole="button" accessibilityLabel={saved ? 'Remove from saved events' : 'Save event'} accessibilityState={{ checked: !!saved, disabled: saving }} disabled={saving}
        onPress={press => { press.stopPropagation(); onToggleSave(); }} style={styles.save}><AppIcon name={saved ? 'bookmark' : 'bookmark-outline'} size={22} color={colors.text} /></Pressable>}
    </View>
    <View style={styles.body}>
      {explanation && <Text style={[styles.reason, premium && styles.premiumReason]} numberOfLines={2}>{explanation}</Text>}
      <Text style={[styles.when, premium && styles.light]}>{availabilityLabel(event)}</Text>
      <Text style={[styles.title, compact && styles.compactTitle, premium && styles.light]} numberOfLines={2}>{event.title}</Text>
      <View style={styles.location}><AppIcon name="location-outline" size={16} color={premium ? tokens.premium.muted : colors.textMuted} /><Text style={[styles.venue, premium && styles.light]} numberOfLines={1}>{event.venue?.name || event.address || 'Bratislava'}</Text></View>
    </View>
  </Pressable>;
  // Web buttons cannot contain another button. Keep the same save position
  // as a sibling overlay; native retains its original nested touch handling.
  const locate = variant !== 'map' && eventCoordinates(event);
  const content = <View style={variant === 'horizontal' ? { width: styles.rail.width + styles.rail.marginRight } : undefined}>
    {card}
    {Platform.OS === 'web' && onToggleSave && <Pressable accessibilityRole="button" accessibilityLabel={saved ? 'Remove from saved events' : 'Save event'} accessibilityState={{ checked: !!saved, disabled: saving }} disabled={saving}
      onPress={press => { press.stopPropagation(); onToggleSave(); }} style={[styles.save,compact&&{right:undefined,left:44}]}><AppIcon name={saved ? 'bookmark' : 'bookmark-outline'} size={22} color={colors.text}/></Pressable>}
    {locate && <Pressable accessibilityRole="button" accessibilityLabel={`View ${event.title} on Map`} onPress={()=>viewOnMap(event)}
      style={{position:'absolute',top:12,left:12,width:36,height:36,borderRadius:18,alignItems:'center',justifyContent:'center',backgroundColor:colors.surface}}>
      <AppIcon name="map-outline" size={18} color={colors.primary}/>
    </Pressable>}
  </View>;
  return initialDelay == null ? content : <Reveal delay={initialDelay}>{content}</Reveal>;
}
const styles = StyleSheet.create({
  card: { marginBottom: 24, borderRadius: tokens.radius.lg, backgroundColor: colors.surface, overflow: 'hidden' },
  heroMedia: { aspectRatio: tokens.image.hero }, railMedia: { aspectRatio: tokens.image.rail }, savedMedia: { aspectRatio: 1.2 }, organizerMedia: { aspectRatio: 2.1 },
  compact: { flexDirection: 'row', marginBottom: 12 }, rail: { width: 270, marginRight: 14 }, premium: { backgroundColor: tokens.premium.surface },
  pressed: { opacity: .9 }, mediaWrap: { aspectRatio: tokens.image.feed, position: 'relative' }, compactMedia: { width: 104, aspectRatio: 1 },
  mediaMeta: { position: 'absolute', bottom: 16, left: 16, right: 16, flexDirection: 'row', justifyContent: 'space-between' },
  tag: { ...tokens.type.caption, color: '#FFFFFF', backgroundColor: tokens.scrim, paddingVertical: 7, paddingHorizontal: 12, borderRadius: 99 },
  save: { position: 'absolute', top: 12, right: 12, width: 48, height: 48, borderRadius: 24, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center' },
  body: { flex: 1, padding: 18, gap: 6 }, reason: { ...tokens.type.caption, color: colors.primaryDark }, when: { ...tokens.type.metadata, color: colors.primaryDark },
  title: { ...tokens.type.section, color: colors.text }, compactTitle: { ...tokens.type.action }, location: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  venue: { ...tokens.type.metadata, color: colors.textMuted, flex: 1 }, light: { color: tokens.premium.text }, premiumReason: { color: tokens.premium.accent },
});
