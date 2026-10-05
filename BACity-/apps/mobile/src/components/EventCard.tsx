import { Ionicons } from '@expo/vector-icons';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import { EventOut } from '../types/event';
import { colors } from '../theme/colors';
import { tokens } from '../theme/tokens';
import { EventMedia } from './EventMedia';

export type EventCardVariant = 'hero' | 'feed' | 'horizontal' | 'compact' | 'map' | 'saved' | 'planner' | 'premium' | 'organizer';
export function EventCard({ event, explanation, saved, saving = false, onToggleSave, variant = 'feed' }: {
  event: EventOut; explanation?: string; saved?: boolean; saving?: boolean; onToggleSave?: () => void; variant?: EventCardVariant;
}) {
  const compact = ['compact', 'map', 'planner'].includes(variant);
  const premium = variant === 'premium';
  const date = new Date(event.start_time);
  return <Pressable accessibilityRole="button" accessibilityLabel={`Open ${event.title}`} onPress={() => router.push('/event/' + event.id)}
    style={({ pressed }) => [styles.card, compact && styles.compact, variant === 'horizontal' && styles.rail, premium && styles.premium, pressed && styles.pressed]}>
    <View style={[styles.mediaWrap, variant === 'hero' && styles.heroMedia, variant === 'horizontal' && styles.railMedia, variant === 'saved' && styles.savedMedia, variant === 'organizer' && styles.organizerMedia, compact && styles.compactMedia]}>
      <EventMedia uri={event.image_url} category={event.category} style={StyleSheet.absoluteFill} />
      {!compact && <View style={styles.mediaMeta}><Text style={styles.tag}>{event.category}</Text><Text style={styles.tag}>{event.price === 0 ? 'Free' : event.price == null ? 'Price unknown' : `${event.price} ${event.currency || 'EUR'}`}</Text></View>}
      {onToggleSave && <Pressable accessibilityRole="button" accessibilityLabel={saved ? 'Remove from saved events' : 'Save event'} accessibilityState={{ checked: !!saved, disabled: saving }} disabled={saving}
        onPress={press => { press.stopPropagation(); onToggleSave(); }} style={styles.save}><Ionicons name={saved ? 'bookmark' : 'bookmark-outline'} size={22} color={colors.text} /></Pressable>}
    </View>
    <View style={styles.body}>
      {explanation && <Text style={[styles.reason, premium && styles.premiumReason]} numberOfLines={2}>{explanation}</Text>}
      <Text style={[styles.when, premium && styles.light]}>{date.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' })} · {date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}</Text>
      <Text style={[styles.title, compact && styles.compactTitle, premium && styles.light]} numberOfLines={2}>{event.title}</Text>
      <View style={styles.location}><Ionicons name="location-outline" size={16} color={premium ? tokens.premium.muted : colors.textMuted} /><Text style={[styles.venue, premium && styles.light]} numberOfLines={1}>{event.venue?.name || event.address || 'Bratislava'}</Text></View>
    </View>
  </Pressable>;
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
