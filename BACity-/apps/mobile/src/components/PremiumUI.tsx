import { themedStyles, useThemeRevision } from '../theme/appearance';
import { ComponentProps, PropsWithChildren } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { AnimatedPressable as Pressable } from './motion/Motion';
import { AppIcon } from "./AppIcon";
import { router } from 'expo-router';
import { EventOut } from '../types/event';
import { tokens } from '../theme/tokens';
import { EventMedia } from './EventMedia';

export function PremiumIntro({ title, subtitle, icon }: { title: string; subtitle: string; icon: ComponentProps<typeof AppIcon>['name'] }) {
  useThemeRevision();
  return <View style={styles.intro}><View style={styles.orbit} /><AppIcon name={icon} size={24} color={tokens.premium.accent} /><Text style={styles.eyebrow}>BACITY+ · CITY, COMPOSED</Text><Text style={styles.title}>{title}</Text><Text style={styles.subtitle}>{subtitle}</Text></View>;
}

/** A chronological stop, not a travel-time claim. All content comes from the planner response. */
export function PlanStop({ event, reason, anchor = false, last = false }: { event: EventOut; reason?: string; anchor?: boolean; last?: boolean }) {
  useThemeRevision();
  const time = new Date(event.start_time).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
  return <View style={styles.stop}>
    <View style={styles.rail}><Text style={styles.time}>{time}</Text><View style={[styles.dot, anchor && styles.anchorDot]} />{!last && <View style={styles.line} />}</View>
    <Pressable accessibilityRole="button" accessibilityLabel={`Open ${event.title}`} onPress={() => router.push('/event/' + event.id)} style={({ pressed }) => [styles.card, pressed && styles.pressed]}>
      <EventMedia uri={event.image_url} category={event.category} style={styles.media} />
      <View style={styles.copy}>{anchor && <Text style={styles.anchor}>YOUR SELECTED EVENT</Text>}<Text style={styles.eventTitle} numberOfLines={3}>{event.title}</Text><Text style={styles.venue}>{event.venue?.name || event.address || 'Bratislava'}</Text>{reason && <Text style={styles.reason}>{reason}</Text>}</View>
    </Pressable>
  </View>;
}

export function PremiumSurface({ children }: PropsWithChildren) {
  useThemeRevision(); return <View style={styles.surface}>{children}</View>; }

const styles = themedStyles(() => ({
  intro: { backgroundColor: tokens.premium.background, paddingVertical: 16, paddingHorizontal: 4, gap: 8, overflow: 'hidden', marginTop: 8, marginBottom: 12 },
  orbit: { position: 'absolute', width: 280, height: 280, borderRadius: 140, borderWidth: 50, borderColor: tokens.premium.surface, right: -130, top: -100 },
  eyebrow: { ...tokens.type.caption, letterSpacing: 1.4, color: tokens.premium.accent }, title: { ...tokens.type.title, color: tokens.premium.text }, subtitle: { ...tokens.type.body, color: tokens.premium.muted },
  surface: { padding: 16, borderRadius: 16, backgroundColor: tokens.premium.surface, gap: 16 },
  stop: { flexDirection: 'row', gap: 12 }, rail: { width: 52, alignItems: 'center' }, time: { ...tokens.type.metadata, color: tokens.premium.muted, marginBottom: 12 },
  dot: { width: 10, height: 10, borderRadius: 5, backgroundColor: tokens.premium.muted }, anchorDot: { backgroundColor: tokens.premium.accent }, line: { flex: 1, width: 1, backgroundColor: tokens.premium.muted, marginVertical: 8, minHeight: 40 },
  card: { flex: 1, flexDirection:'row', borderRadius: 16, overflow: 'hidden', marginBottom: 12, backgroundColor: tokens.premium.surface }, media: { width: 72, minHeight: 90 }, copy: { flex: 1, padding: 12, gap: 6 },
  eventTitle: { ...tokens.type.action, color: tokens.premium.text }, venue: { ...tokens.type.metadata, color: tokens.premium.muted }, reason: { ...tokens.type.metadata, color: tokens.premium.accent }, anchor: { ...tokens.type.caption, color: tokens.premium.accent }, pressed: { opacity: .85 },
}));
