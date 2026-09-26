import { ComponentProps, PropsWithChildren } from "react";
import { Image, Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { colors } from "../theme/colors";
import { fonts } from "../theme/fonts";

type IconName = ComponentProps<typeof Ionicons>["name"];

export function Avatar({ uri, name, size = 48 }: { uri?: string | null; name?: string | null; size?: number }) {
  const initials = (name || "BA").split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]?.toUpperCase()).join("");
  return uri ? <Image source={{ uri }} style={{ width: size, height: size, borderRadius: size * .36, backgroundColor: colors.primarySoft }} /> : (
    <View style={[styles.avatar, { width: size, height: size, borderRadius: size * .36 }]}>
      <Text style={[styles.avatarText, { fontSize: Math.max(11, size * .3) }]}>{initials}</Text>
    </View>
  );
}

export function IconButton({ icon, label, onPress, badge = false }: { icon: IconName; label: string; onPress: () => void; badge?: boolean }) {
  return <Pressable accessibilityRole="button" accessibilityLabel={label} hitSlop={6} onPress={onPress} style={({ pressed }) => [styles.iconButton, pressed && styles.pressed]}>
    <Ionicons name={icon} size={21} color={colors.text} />
    {badge && <View style={styles.badge} />}
  </Pressable>;
}

export function ScreenHeader({ title, back = true, right }: { title: string; back?: boolean; right?: React.ReactNode }) {
  return <View style={styles.header}>
    {back ? <IconButton icon="chevron-back" label="Go back" onPress={() => router.canGoBack() ? router.back() : router.replace("/(tabs)/discover")} /> : <View style={styles.headerSlot} />}
    <Text style={styles.headerTitle} numberOfLines={1}>{title}</Text>
    <View style={styles.headerSlot}>{right}</View>
  </View>;
}

export function SectionHeader({ title, action, onAction }: { title: string; action?: string; onAction?: () => void }) {
  return <View style={styles.sectionHeader}><Text style={styles.sectionTitle}>{title}</Text>{action && onAction && <Pressable onPress={onAction}><Text style={styles.sectionAction}>{action}</Text></Pressable>}</View>;
}

export function Stat({ value, label, onPress }: { value: string | number; label: string; onPress?: () => void }) {
  const content = <><Text style={styles.statValue} numberOfLines={1}>{value}</Text><Text style={styles.statLabel}>{label}</Text></>;
  return onPress ? <Pressable accessibilityRole="button" onPress={onPress} style={({ pressed }) => [styles.stat, pressed && styles.pressed]}>{content}</Pressable> : <View style={styles.stat}>{content}</View>;
}

export function ProfileRow({ profile, subtitle, action, onAction, onPress }: { profile: any; subtitle?: string; action?: string; onAction?: () => void; onPress: () => void }) {
  return <Pressable onPress={onPress} style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}>
    <Avatar uri={profile.avatar_url} name={profile.display_name || profile.name} />
    <View style={styles.rowCopy}><Text style={styles.rowTitle} numberOfLines={1}>{profile.display_name || profile.name || "BACity member"}</Text><Text style={styles.rowSubtitle} numberOfLines={1}>{subtitle || profile.neighborhood || profile.reputation_level || "Bratislava"}</Text></View>
    {action && onAction ? <Pressable accessibilityRole="button" onPress={(event) => { event.stopPropagation(); onAction(); }} style={({ pressed }) => [styles.smallAction, pressed && styles.pressed]}><Text style={styles.smallActionText}>{action}</Text></Pressable> : <Ionicons name="chevron-forward" size={17} color={colors.textMuted} />}
  </Pressable>;
}

export function ListItem({ icon, title, subtitle, onPress, trailing }: { icon: IconName; title: string; subtitle?: string | null; onPress?: () => void; trailing?: React.ReactNode }) {
  const content = <>
    <View style={styles.listIcon}><Ionicons name={icon} size={20} color={colors.primaryDark} /></View>
    <View style={styles.rowCopy}><Text style={styles.rowTitle} numberOfLines={1}>{title}</Text>{subtitle ? <Text style={styles.rowSubtitle} numberOfLines={2}>{subtitle}</Text> : null}</View>
    {trailing ?? (onPress ? <Ionicons name="chevron-forward" size={17} color={colors.textMuted} /> : null)}
  </>;
  return onPress ? <Pressable onPress={onPress} style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}>{content}</Pressable> : <View style={styles.row}>{content}</View>;
}

export function SkeletonList({ rows = 5 }: { rows?: number }) {
  return <View>{Array.from({ length: rows }).map((_, index) => <View key={index} style={styles.skeletonRow}><View style={styles.skeletonAvatar} /><View style={styles.skeletonCopy}><View style={styles.skeletonWide} /><View style={styles.skeletonShort} /></View></View>)}</View>;
}

export function OverflowMenu({ visible, title = "More", onClose, children }: PropsWithChildren<{ visible: boolean; title?: string; onClose: () => void }>) {
  return <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
    <Pressable style={styles.overlay} onPress={onClose}>
      <Pressable style={styles.sheet} onPress={event => event.stopPropagation()}>
        <View style={styles.sheetHandle} /><View style={styles.sheetTitleRow}><Text style={styles.sheetTitle}>{title}</Text><IconButton icon="close" label="Close menu" onPress={onClose} /></View>
        <ScrollView contentContainerStyle={styles.sheetContent}>{children}</ScrollView>
      </Pressable>
    </Pressable>
  </Modal>;
}

const styles = StyleSheet.create({
  avatar: { backgroundColor: colors.primary, alignItems: "center", justifyContent: "center" },
  avatarText: { color: colors.white, fontFamily: fonts.black },
  iconButton: { width: 44, height: 44, borderRadius: 16, alignItems: "center", justifyContent: "center" },
  pressed: { opacity: .68, transform: [{ scale: .96 }] },
  badge: { position: "absolute", right: 7, top: 7, width: 8, height: 8, borderRadius: 4, backgroundColor: colors.primary, borderWidth: 2, borderColor: colors.background },
  header: { minHeight: 58, flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 8 },
  headerSlot: { width: 44, alignItems: "flex-end" },
  headerTitle: { flex: 1, textAlign: "center", color: colors.text, fontFamily: fonts.black, fontSize: 17 },
  sectionHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: 20, marginBottom: 10 },
  sectionTitle: { color: colors.text, fontFamily: fonts.black, fontSize: 19, letterSpacing: -.4 },
  sectionAction: { color: colors.primaryDark, fontFamily: fonts.semibold, fontSize: 12 },
  stat: { flex: 1, minWidth: 78, alignItems: "center", paddingVertical: 10 },
  statValue: { color: colors.text, fontFamily: fonts.black, fontSize: 17 },
  statLabel: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 10, marginTop: 2 },
  row: { minHeight: 68, flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 10, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  rowPressed: { backgroundColor: colors.surfaceAlt },
  rowCopy: { flex: 1, minWidth: 0 },
  rowTitle: { color: colors.text, fontFamily: fonts.semibold, fontSize: 14 },
  rowSubtitle: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 11, lineHeight: 16, marginTop: 2 },
  smallAction: { minHeight: 36, paddingHorizontal: 13, borderRadius: 13, backgroundColor: colors.primarySoft, alignItems: "center", justifyContent: "center" },
  smallActionText: { color: colors.primaryDark, fontFamily: fonts.semibold, fontSize: 10 },
  listIcon: { width: 44, height: 44, borderRadius: 16, backgroundColor: colors.primarySoft, alignItems: "center", justifyContent: "center" },
  skeletonRow: { height: 68, flexDirection: "row", alignItems: "center", gap: 12 },
  skeletonAvatar: { width: 48, height: 48, borderRadius: 17, backgroundColor: colors.primarySoft },
  skeletonCopy: { flex: 1, gap: 8 },
  skeletonWide: { width: "62%", height: 12, borderRadius: 6, backgroundColor: colors.primarySoft },
  skeletonShort: { width: "38%", height: 9, borderRadius: 5, backgroundColor: colors.surfaceAlt },
  overlay: { flex: 1, justifyContent: "flex-end", backgroundColor: "rgba(39,35,41,.3)" },
  sheet: { maxHeight: "78%", backgroundColor: colors.background, borderTopLeftRadius: 28, borderTopRightRadius: 28, paddingHorizontal: 18, paddingBottom: 30 },
  sheetHandle: { width: 40, height: 4, borderRadius: 2, backgroundColor: colors.border, alignSelf: "center", marginTop: 9 },
  sheetTitleRow: { minHeight: 58, flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  sheetTitle: { color: colors.text, fontFamily: fonts.black, fontSize: 20 },
  sheetContent: { paddingBottom: 10 },
});
