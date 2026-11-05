import { useNavRow } from './interactions/NavListCard';
import { AppSheet } from './sheets/AppSheet';
import { useNavigation, usePathname } from 'expo-router';
import { useLayoutEffect } from 'react';
import { themedStyles, useThemeRevision } from '../theme/appearance';
import { NumberTicker } from './interactions/NumberTicker';
import { ComponentProps, PropsWithChildren, useEffect, useState } from "react";
import { Image, KeyboardAvoidingView, Modal, Platform, ScrollView, StyleSheet, Text, View } from "react-native";
import { AnimatedPressable as Pressable } from './motion/Motion';
import { AppIcon } from "./AppIcon";
import { router } from "expo-router";
import { colors } from "../theme/colors";
import { fonts } from "../theme/fonts";
import { tokens } from "../theme/tokens";
import { SkeletonPulse } from './motion/Motion';
import { useReducedMotion } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

type IconName = ComponentProps<typeof AppIcon>["name"];

export function Avatar({ uri, name, size = 48 }: { uri?: string | null; name?: string | null; size?: number }) {
  useThemeRevision();
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [uri]);
  const initials = (name || "BA").split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]?.toUpperCase()).join("");
  return uri && !failed ? <Image onError={() => setFailed(true)} accessibilityLabel={name || 'Member avatar'} source={{ uri }} style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: colors.primarySoft }} /> : (
    <View style={[styles.avatar, { width: size, height: size, borderRadius: size / 2 }]}>
      <Text style={[styles.avatarText, { fontSize: Math.max(11, size * .3) }]}>{initials}</Text>
    </View>
  );
}

export function IconButton({ icon, label, onPress, badge = false }: { icon: IconName; label: string; onPress: () => void; badge?: boolean }) {
  useThemeRevision();
  return <Pressable accessibilityRole="button" accessibilityLabel={label} hitSlop={6} onPress={onPress} style={({ pressed }) => [styles.iconButton, pressed && styles.pressed]}>
    <AppIcon name={icon} size={21} color={colors.text} />
    {badge && <View style={styles.badge} />}
  </Pressable>;
}

export function ScreenHeader({ title, back = true, right }: { title: string; back?: boolean; right?: React.ReactNode }) {
  useThemeRevision();
  const navigation = useNavigation(); const pathname = usePathname();
  const inTabs = ['/discover', '/explore', '/profile', '/map', '/saved', '/contribute'].includes(pathname);
  useLayoutEffect(() => { if (!inTabs) navigation.setOptions({ title, headerRight: () => right ?? null }); }, [navigation, title, right, inTabs]);
  if (!inTabs) return null;
  return <View style={styles.header}>
    {back ? <IconButton icon="chevron-back" label="Go back" onPress={() => router.canGoBack() ? router.back() : router.replace("/(tabs)/discover")} /> : <View style={styles.headerSlot} />}
    <Text style={styles.headerTitle} numberOfLines={1}>{title}</Text>
    <View style={styles.headerSlot}>{right}</View>
  </View>;
}

export function SectionHeader({ title, action, onAction }: { title: string; action?: string; onAction?: () => void }) {
  useThemeRevision();
  return <View style={styles.sectionHeader}><Text style={styles.sectionTitle}>{title}</Text>{action && onAction && <Pressable accessibilityRole="button" accessibilityLabel={action} onPress={onAction} style={{ minHeight: 48, justifyContent: 'center', paddingLeft: 12 }}><Text style={styles.sectionAction}>{action}</Text></Pressable>}</View>;
}

export function Stat({ value, label, onPress }: { value: string | number; label: string; onPress?: () => void }) {
  useThemeRevision();
  const content = <>{typeof value === 'number' ? <NumberTicker value={value} label={label} style={styles.statValue} /> : <Text style={styles.statValue}>{value}</Text>}<Text style={styles.statLabel}>{label}</Text></>;
  return onPress ? <Pressable accessibilityRole="button" accessibilityLabel={`${value} ${label}`} onPress={onPress} style={({ pressed }) => [styles.stat, pressed && styles.pressed]}>{content}</Pressable> : <View style={styles.stat}>{content}</View>;
}

export function ProfileRow({ profile, subtitle, action, onAction, onPress }: { profile: any; subtitle?: string; action?: string; onAction?: () => void; onPress: () => void }) {
  useThemeRevision();
  return <Pressable accessibilityRole="button" accessibilityLabel={`Open ${profile.display_name || profile.name || 'member'} profile`} onPress={onPress} style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}>
    <Avatar uri={profile.avatar_url} name={profile.display_name || profile.name} />
    <View style={styles.rowCopy}><Text style={styles.rowTitle} numberOfLines={1}>{profile.display_name || profile.name || "BACity member"}</Text><Text style={styles.rowSubtitle} numberOfLines={1}>{subtitle || profile.neighborhood || profile.reputation_level || "Bratislava"}</Text></View>
    {action && onAction ? <Pressable accessibilityRole="button" onPress={(event) => { event.stopPropagation(); onAction(); }} style={({ pressed }) => [styles.smallAction, pressed && styles.pressed]}><Text style={styles.smallActionText}>{action}</Text></Pressable> : <AppIcon name="chevron-forward" size={17} color={colors.textMuted} />}
  </Pressable>;
}

export function ListItem({ icon, title, subtitle, onPress, trailing }: { icon: IconName; title: string; subtitle?: string | null; onPress?: () => void; trailing?: React.ReactNode }) {
  useThemeRevision();
  const navRow = useNavRow();
  const content = <>
    <View style={styles.listIcon}><AppIcon name={icon} size={20} color={colors.primaryDark} /></View>
    <View style={styles.rowCopy}><Text style={styles.rowTitle}>{title}</Text>{subtitle ? <Text style={styles.rowSubtitle} numberOfLines={2}>{subtitle}</Text> : null}</View>
    {trailing ?? (onPress ? <AppIcon name="chevron-forward" size={17} color={colors.textMuted} /> : null)}
  </>;
  return onPress ? <Pressable {...navRow} accessibilityRole="button" accessibilityLabel={title} onPress={onPress} style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}>{content}</Pressable> : <View style={styles.row}>{content}</View>;
}

export function SkeletonList({ rows = 5 }: { rows?: number }) {
  useThemeRevision();
  return <SkeletonPulse>{Array.from({ length: rows }).map((_, index) => <View key={index} style={styles.skeletonRow}><View style={styles.skeletonAvatar} /><View style={styles.skeletonCopy}><View style={styles.skeletonWide} /><View style={styles.skeletonShort} /></View></View>)}</SkeletonPulse>;
}

export function OverflowMenu({ visible, title = "More", onClose, children }: PropsWithChildren<{ visible: boolean; title?: string; onClose: () => void }>) {
  useThemeRevision();
  return <AppSheet visible={visible} title={title} onClose={onClose}>{children}</AppSheet>;
}

const styles = themedStyles(() => ({
  avatar: { backgroundColor: colors.primary, alignItems: "center", justifyContent: "center" },
  avatarText: { color: colors.white, fontFamily: fonts.black },
  iconButton: { width: 48, height: 48, borderRadius: 24, alignItems: "center", justifyContent: "center" },
  pressed: { opacity: .68 },
  badge: { position: "absolute", right: 7, top: 7, width: 8, height: 8, borderRadius: 4, backgroundColor: colors.primary, borderWidth: 2, borderColor: colors.background },
  header: { minHeight: 58, flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 8 },
  headerSlot: { width: 44, alignItems: "flex-end" },
  headerTitle: { flex: 1, textAlign: "center", color: colors.text, ...tokens.type.action },
  sectionHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: 20, marginBottom: 10 },
  sectionTitle: { color: colors.text, ...tokens.type.section, flexShrink: 1 },
  sectionAction: { color: colors.primaryDark, fontFamily: fonts.semibold, fontSize: 12 },
  stat: { flex: 1, minWidth: 64, alignItems: "center", paddingVertical: 8 },
  statValue: { color: colors.text, ...tokens.type.action, fontSize: 19 },
  statLabel: { color: colors.textMuted, ...tokens.type.caption, marginTop: 2 },
  row: { minHeight: 56, flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 10, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  rowPressed: { backgroundColor: colors.surfaceAlt },
  rowCopy: { flex: 1, minWidth: 0 },
  rowTitle: { color: colors.text, ...tokens.type.action },
  rowSubtitle: { color: colors.textMuted, ...tokens.type.metadata, marginTop: 4 },
  smallAction: { minHeight: 48, paddingHorizontal: 16, borderRadius: 22, backgroundColor: colors.primarySoft, alignItems: "center", justifyContent: "center" },
  smallActionText: { color: colors.primaryDark, ...tokens.type.caption },
  listIcon: { width: 28, height: 32, alignItems: "center", justifyContent: "center" },
  skeletonRow: { height: 68, flexDirection: "row", alignItems: "center", gap: 12 },
  skeletonAvatar: { width: 48, height: 48, borderRadius: 17, backgroundColor: colors.primarySoft },
  skeletonCopy: { flex: 1, gap: 8 },
  skeletonWide: { width: "62%", height: 12, borderRadius: 6, backgroundColor: colors.primarySoft },
  skeletonShort: { width: "38%", height: 9, borderRadius: 5, backgroundColor: colors.surfaceAlt },
  overlay: { flex: 1, justifyContent: "flex-end", backgroundColor: tokens.scrim },
  sheet: { maxHeight: "78%", backgroundColor: colors.background, borderTopLeftRadius: 28, borderTopRightRadius: 28, paddingHorizontal: 18, paddingBottom: 30 },
  sheetHandle: { width: 40, height: 4, borderRadius: 2, backgroundColor: colors.border, alignSelf: "center", marginTop: 9 },
  sheetTitleRow: { minHeight: 58, flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  sheetTitle: { color: colors.text, fontFamily: fonts.black, fontSize: 20 },
  sheetContent: { paddingBottom: 10 },
}));
