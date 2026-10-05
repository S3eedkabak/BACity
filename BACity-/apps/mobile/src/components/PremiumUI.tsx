import { ComponentProps, PropsWithChildren } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { EventOut } from '../types/event';
import { tokens } from '../theme/tokens';
import { EventMedia } from './EventMedia';

export function PremiumIntro({ title, subtitle, icon }: { title: string; subtitle: string; icon: ComponentProps<typeof Ionicons>['name'] }) {
  return <View style={styles.intro}><View style={styles.orbit} /><Ionicons name={icon} size={32} color={tokens.premium.accent} /><Text style={styles.eyebrow}>BACITY+ · CITY, COMPOSED</Text><Text style={styles.title}>{title}</Text><Text style={styles.subtitle}>{subtitle}</Text></View>;
}

/** A chronological stop, not a travel-time claim. All content comes from the planner response. */
export function PlanStop({ event, reason, anchor = false, last = false }: { event: EventOut; reason?: string; anchor?: boolean; last?: boolean }) {
  const time = new Date(event.start_time).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
  return <View style={styles.stop}>
    <View style={styles.rail}><Text style={styles.time}>{time}</Text><View style={[styles.dot, anchor && styles.anchorDot]} />{!last && <View style={styles.line} />}</View>
    <Pressable accessibilityRole="button" accessibilityLabel={`Open ${event.title}`} onPress={() => router.push('/event/' + event.id)} style={({ pressed }) => [styles.card, pressed && styles.pressed]}>
      <EventMedia uri={event.image_url} category={event.category} style={styles.media} />
      <View style={styles.copy}>{anchor && <Text style={styles.anchor}>YOUR SELECTED EVENT</Text>}<Text style={styles.eventTitle} numberOfLines={3}>{event.title}</Text><Text style={styles.venue}>{event.venue?.name || event.address || 'Bratislava'}</Text>{reason && <Text style={styles.reason}>{reason}</Text>}</View>
    </Pressable>
  </View>;
}

export function PremiumSurface({ children }: PropsWithChildren) { return <View style={styles.surface}>{children}</View>; }

const styles = StyleSheet.create({
  intro: { backgroundColor: tokens.premium.background, padding: 28, borderRadius: 32, gap: 12, overflow: 'hidden', marginTop: 12, marginBottom: 24 },
  orbit: { position: 'absolute', width: 280, height: 280, borderRadius: 140, borderWidth: 50, borderColor: tokens.premium.surface, right: -130, top: -100 },
  eyebrow: { ...tokens.type.caption, letterSpacing: 1.4, color: tokens.premium.accent }, title: { ...tokens.type.hero, color: tokens.premium.text }, subtitle: { ...tokens.type.body, color: tokens.premium.muted },
  surface: { padding: 24, borderRadius: 28, backgroundColor: tokens.premium.surface, gap: 16 },
  stop: { flexDirection: 'row', gap: 12 }, rail: { width: 52, alignItems: 'center' }, time: { ...tokens.type.caption, color: tokens.premium.background, marginBottom: 12 },
  dot: { width: 10, height: 10, borderRadius: 5, backgroundColor: tokens.premium.muted }, anchorDot: { backgroundColor: '#C94758' }, line: { flex: 1, width: 1, backgroundColor: tokens.premium.muted, marginVertical: 8, minHeight: 40 },
  card: { flex: 1, borderRadius: 24, overflow: 'hidden', marginBottom: 20, backgroundColor: tokens.premium.surface }, media: { aspectRatio: 1.8 }, copy: { padding: 18, gap: 7 },
  eventTitle: { ...tokens.type.section, color: tokens.premium.text }, venue: { ...tokens.type.metadata, color: tokens.premium.muted }, reason: { ...tokens.type.metadata, color: tokens.premium.accent }, anchor: { ...tokens.type.caption, color: tokens.premium.accent }, pressed: { opacity: .85 },
});
