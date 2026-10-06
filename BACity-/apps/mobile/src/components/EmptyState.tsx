import { AppIcon } from "./AppIcon";
import { StyleSheet, Text, View } from "react-native";
import { AnimatedPressable as Pressable } from './motion/Motion';
import { colors } from "../theme/colors";
import { fonts } from "../theme/fonts";
import { tokens } from '../theme/tokens';
import { CharacterScene, CharacterMood } from './illustrations/CharacterScene';
import { Reveal } from './motion/Motion';

export function EmptyState({
  title,
  subtitle,
  action,
  onAction,
  scene,
}: {
  title: string;
  subtitle?: string;
  action?: string;
  onAction?: () => void;
  scene?: CharacterMood;
}) {
  return (
    <View style={styles.wrap}>
      {scene ? <Reveal><CharacterScene mood={scene} size={180} /></Reveal> : <View style={styles.icon}>
        <AppIcon name="sparkles-outline" size={24} color={colors.primaryDark} />
      </View>}
      <Text style={styles.title}>{title}</Text>
      {!!subtitle && <Text style={styles.subtitle}>{subtitle}</Text>}
      {!!action && !!onAction && (
        <Pressable accessibilityRole="button" style={({ pressed }) => [styles.button, pressed && { opacity: .8 }]} onPress={onAction}>
          <Text style={styles.buttonText}>{action}</Text>
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    minHeight: 280,
    paddingHorizontal: 34,
    alignItems: "center",
    justifyContent: "center",
  },
  icon: {
    width: 56,
    height: 56,
    borderRadius: 20,
    backgroundColor: colors.primarySoft,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 16,
  },
  title: {
    ...tokens.type.section,
    color: colors.text,
    fontFamily: fonts.black,
    fontSize: 21,
    letterSpacing: -0.5,
    textAlign: "center",
  },
  subtitle: {
    ...tokens.type.body,
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 13,
    lineHeight: 19,
    textAlign: "center",
    marginTop: 7,
  },
  button: {
    marginTop: 18,
    minHeight: 46,
    paddingHorizontal: 20,
    borderRadius: 16,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  buttonText: { color: colors.white, fontFamily: fonts.semibold, fontSize: 13 },
});
