import { ContentStages } from "./navigation/SceneMotion";
import Animated, { LinearTransition, useAnimatedStyle, useSharedValue, withTiming } from 'react-native-reanimated';
import { useMotionPreference } from './interactions/useMotionPreference';
import { useEffect } from 'react';
import { useNavigation } from 'expo-router';
import { useLayoutEffect } from 'react';
import { themedStyles, useThemeRevision } from '../theme/appearance';
import { MorphActionButton } from './interactions/ActionButton';
import { AppTextField } from './interactions/AppTextField';
import { ComponentProps, PropsWithChildren, useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View } from "react-native";
import { AnimatedPressable as Pressable } from './motion/Motion';
import { SafeAreaView } from "react-native-safe-area-context";
import { AppIcon } from "./AppIcon";
import { router } from "expo-router";
import { BrandMark } from "./BrandMark";
import { colors } from "../theme/colors";
import { fonts } from "../theme/fonts";
import { tokens } from '../theme/tokens';

export function Page({ title, children }: PropsWithChildren<{ title: string }>) {
  useThemeRevision();
  const navigation = useNavigation();
  useLayoutEffect(() => { navigation.setOptions({ title }); }, [navigation, title]);
  return (
    <SafeAreaView style={ui.safe} edges={["bottom"]}>
      <KeyboardAvoidingView style={ui.safe} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView
        contentContainerStyle={ui.page}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <ContentStages>{children}</ContentStages>
      </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

export function Card({ children }: PropsWithChildren) {
  useThemeRevision();
  return <View style={ui.card}>{children}</View>;
}

export function Disclosure({ title, icon = 'options-outline', initiallyOpen = false, children }: PropsWithChildren<{ title: string; icon?: ComponentProps<typeof AppIcon>['name']; initiallyOpen?: boolean }>) {
  useThemeRevision();
  const [open, setOpen] = useState(initiallyOpen); const reduced=useMotionPreference(); const rotation=useSharedValue(initiallyOpen?180:0);
  useEffect(()=>{rotation.value=withTiming(open?180:0,{duration:reduced?0:240});},[open,reduced,rotation]);
  const chevron=useAnimatedStyle(()=>({transform:[{rotate:`${rotation.value}deg`}]}));
  return <Animated.View layout={reduced?undefined:LinearTransition.duration(240)} style={ui.disclosure}><Pressable accessibilityRole="button" accessibilityState={{ expanded: open }} accessibilityLabel={title} onPress={() => setOpen(value => !value)} style={ui.disclosureHeader}><AppIcon name={icon} size={24} color={colors.primaryDark} /><Text style={ui.disclosureTitle}>{title}</Text><Animated.View style={chevron}><AppIcon name="chevron-down" size={18} color={colors.textMuted} /></Animated.View></Pressable>{open && <View style={ui.disclosureBody}>{children}</View>}</Animated.View>;
}

export function Button({
  title,
  onPress,
  busy = false,
  variant = 'primary',
}: {
  title: string;
  onPress: () => void;
  busy?: boolean;
  variant?: 'primary' | 'secondary' | 'danger';
}) {
  useThemeRevision();
  return <MorphActionButton title={title} onPress={onPress} state={busy ? 'loading' : 'idle'} variant={variant} />;
}

export function Field({
  label,
  value,
  onChange,
  multiline,
  secure,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  multiline?: boolean;
  secure?: boolean;
}) {
  useThemeRevision();
  return <AppTextField label={label} value={value} onChangeText={onChange} multiline={multiline} secure={secure} autoCapitalize="none" />;
}

export function Chip({
  title,
  active = false,
  onPress,
}: {
  title: string;
  active?: boolean;
  onPress: () => void;
}) {
  useThemeRevision();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected: active }}
      onPress={onPress}
      style={({ pressed }) => [
        ui.chip,
        active && ui.chipActive,
        pressed && ui.pressed,
      ]}
    >
      <Text style={[ui.chipText, active && ui.chipTextActive]}>{title}</Text>
    </Pressable>
  );
}

export function Notice({ text }: { text: string | null | undefined }) {
  useThemeRevision();
  return text ? (
    <View style={ui.noticeBox}>
      <AppIcon name="information-circle-outline" size={17} color={colors.primaryDark} />
      <Text accessibilityRole="alert" style={ui.notice}>
        {text}
      </Text>
    </View>
  ) : null;
}

export const ui = themedStyles(() => ({
  disclosure: { borderBottomWidth: StyleSheet.hairlineWidth, borderColor: colors.border },
  disclosureHeader: { minHeight: 64, flexDirection: 'row', alignItems: 'center', gap: 16 },
  disclosureTitle: { ...tokens.type.action, flex: 1, color: colors.text },
  disclosureBody: { gap: 14, paddingBottom: 24 },
  buttonSecondary: { backgroundColor: colors.surfaceAlt, shadowOpacity: 0 },
  buttonSecondaryText: { color: colors.primaryDark },
  buttonDanger: { backgroundColor: colors.danger },
  safe: { flex: 1, backgroundColor: colors.background },
  page: {
    width: '100%',
    maxWidth: tokens.layout.maxWidth,
    alignSelf: 'center',
    paddingHorizontal: 18,
    gap: 14,
    backgroundColor: colors.background,
    flexGrow: 1,
    paddingBottom: 112,
  },
  topbar: {
    minHeight: 52,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  back: {
    width: tokens.icon.touch,
    height: tokens.icon.touch,
    borderRadius: 15,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  pressed: { opacity: 0.7 },
  topbarSpacer: { width: 40 },
  title: {
    ...tokens.type.hero,
    fontWeight: '800',
    fontSize: 24,
    lineHeight: 30,
    letterSpacing: -1,
    fontFamily: fonts.black,
    color: colors.text,
    marginTop: 4,
    marginBottom: 2,
  },
  heading: {
    fontWeight: '700',
    fontSize: 18,
    lineHeight: 22,
    fontFamily: fonts.black,
    color: colors.text,
    letterSpacing: -0.35,
  },
  text: {
    ...tokens.type.body,
    fontFamily: fonts.regular,
    color: colors.text,
  },
  muted: {
    ...tokens.type.metadata,
    fontFamily: fonts.regular,
    color: colors.textMuted,
  },
  card: {
    padding: 20,
    borderRadius: 20,
    backgroundColor: colors.surface,
    gap: 11,
    shadowColor: colors.shadow,
    shadowOpacity: 0,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 7 },
    elevation: 0,
  },
  field: { gap: 7 },
  label: {
    color: colors.textMuted,
    fontFamily: fonts.semibold,
    fontSize: 12,
    letterSpacing: 0.65,
    textTransform: "uppercase",
  },
  input: {
    minHeight: 52,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 17,
    paddingHorizontal: 15,
    paddingVertical: 13,
    color: colors.text,
    backgroundColor: colors.surfaceAlt,
    fontFamily: fonts.regular,
    fontSize: 14,
  },
  inputMultiline: { minHeight: 110, textAlignVertical: "top" },
  button: {
    backgroundColor: colors.primary,
    paddingHorizontal: 16,
    paddingVertical: 13,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 48,
    shadowColor: colors.primaryDark,
    shadowOpacity: 0,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
  },
  buttonPressed: { opacity: 0.92 },
  disabled: { opacity: 0.55 },
  buttonText: {
    fontWeight: '600',
    color: colors.white,
    fontFamily: fonts.semibold,
    fontSize: 15,
    textAlign: "center",
  },
  chip: {
    minHeight: 48,
    paddingHorizontal: 14,
    borderRadius: 18,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  chipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  chipText: {
    fontWeight: '600',
    color: colors.textMuted,
    fontFamily: fonts.semibold,
    fontSize: 13,
  },
  chipTextActive: { color: colors.white },
  noticeBox: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
    padding: 12,
    borderRadius: 16,
    backgroundColor: colors.primarySoft,
  },
  notice: {
    flex: 1,
    color: colors.primaryDark,
    fontFamily: fonts.medium,
    fontSize: 12,
    lineHeight: 18,
  },
  row: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
}));
