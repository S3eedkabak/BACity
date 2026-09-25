import { StyleProp, StyleSheet, Text, TextStyle, View } from "react-native";
import { colors } from "../theme/colors";
import { fonts } from "../theme/fonts";

export function BrandMark({
  light = false,
  compact = false,
  style,
}: {
  light?: boolean;
  compact?: boolean;
  style?: StyleProp<TextStyle>;
}) {
  return (
    <View style={styles.row} accessibilityLabel="BACity">
      <Text
        style={[
          styles.wordmark,
          compact && styles.compact,
          light && styles.light,
          style,
        ]}
      >
        BA<Text style={styles.accent}>City</Text>
      </Text>
      <View style={[styles.dot, compact && styles.dotCompact]} />
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center" },
  wordmark: {
    color: colors.text,
    fontFamily: fonts.black,
    fontSize: 44,
    letterSpacing: -2,
  },
  compact: { fontSize: 24, letterSpacing: -1 },
  light: { color: colors.white },
  accent: { color: colors.primary },
  dot: {
    width: 9,
    height: 9,
    borderRadius: 5,
    backgroundColor: colors.primary,
    marginLeft: 5,
    marginTop: 14,
  },
  dotCompact: { width: 6, height: 6, marginTop: 8, marginLeft: 3 },
});
