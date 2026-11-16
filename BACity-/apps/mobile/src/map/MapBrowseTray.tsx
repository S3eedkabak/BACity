import { Text, View } from "react-native";
import { AnimatedPressable } from "../components/motion/Motion";
import { AppIcon } from "../components/AppIcon";
import { themedStyles, useThemeRevision } from "../theme/appearance";
import { colors } from "../theme/colors";
import { tokens } from "../theme/tokens";

/** Map composition owns only presentation; viewport, camera and filters stay with MapScreen. */
export function MapBrowseTray({
  countLabel,
  appliedLabels,
  expanded,
  onPress,
}: {
  countLabel: string;
  appliedLabels: string[];
  expanded: boolean;
  onPress: () => void;
}) {
  useThemeRevision();
  const applied = appliedLabels.length > 0;
  const ink = applied ? colors.textInverse : colors.text;
  return (
    <AnimatedPressable
      accessibilityRole="button"
      accessibilityLabel={
        "Map event filters and area events" +
        (applied
          ? ". Applied: " + appliedLabels.join(", ")
          : ". No filters applied")
      }
      accessibilityState={{ expanded }}
      onPress={onPress}
      style={[styles.tray, applied && { backgroundColor: colors.text }]}
    >
      <AppIcon
        name={applied ? "options-outline" : "calendar-outline"}
        size={22}
        color={applied ? ink : colors.primaryDark}
      />
      <View style={styles.copy}>
        <Text style={[styles.title, { color: ink }]}>{countLabel}</Text>
        <Text
          numberOfLines={1}
          style={[styles.subtitle, applied && { color: ink }]}
        >
          {applied ? appliedLabels.join(" · ") : "All events · Filters"}
        </Text>
      </View>
      <AppIcon
        name="chevron-up"
        size={18}
        color={applied ? ink : colors.textMuted}
      />
    </AnimatedPressable>
  );
}
const styles = themedStyles(() => ({
  tray: {
    position: "absolute",
    bottom: tokens.space.md,
    left: tokens.layout.gutter,
    right: 76,
    minHeight: 68,
    paddingHorizontal: tokens.space.control,
    paddingVertical: tokens.space.md,
    borderRadius: tokens.radius.card,
    backgroundColor: colors.background,
    shadowOpacity: 0.15,
    shadowRadius: 12,
    flexDirection: "row",
    alignItems: "center",
    gap: tokens.space.md,
  },
  copy: { flex: 1, minWidth: 0 },
  title: { ...tokens.type.action },
  subtitle: {
    ...tokens.type.caption,
    color: colors.textMuted,
    marginTop: tokens.space.xs,
  },
}));
