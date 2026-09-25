import { useEffect, useRef } from "react";
import { Animated, StyleSheet, View } from "react-native";
import { colors } from "../theme/colors";

export function LoadingState() {
  const pulse = useRef(new Animated.Value(0.45)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 0.95, duration: 650, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0.45, duration: 650, useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [pulse]);

  return (
    <View style={styles.page}>
      <Animated.View style={[styles.hero, { opacity: pulse }]} />
      <View style={styles.row}>
        <Animated.View style={[styles.chip, { opacity: pulse }]} />
        <Animated.View style={[styles.chip, { opacity: pulse }]} />
        <Animated.View style={[styles.chip, { opacity: pulse }]} />
      </View>
      {[0, 1, 2].map((item) => (
        <Animated.View key={item} style={[styles.card, { opacity: pulse }]}>
          <View style={styles.image} />
          <View style={styles.copy}>
            <View style={styles.lineWide} />
            <View style={styles.line} />
            <View style={styles.lineShort} />
          </View>
        </Animated.View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.background, padding: 18, paddingTop: 26 },
  hero: { height: 44, width: "68%", borderRadius: 15, backgroundColor: colors.primarySoft },
  row: { flexDirection: "row", gap: 8, marginVertical: 22 },
  chip: { width: 78, height: 34, borderRadius: 17, backgroundColor: colors.primarySoft },
  card: {
    height: 118,
    borderRadius: 24,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: 12,
    padding: 10,
    flexDirection: "row",
  },
  image: { width: 98, height: 98, borderRadius: 18, backgroundColor: colors.surfaceAlt },
  copy: { flex: 1, padding: 10, gap: 9 },
  lineWide: { height: 13, width: "88%", borderRadius: 7, backgroundColor: colors.primarySoft },
  line: { height: 10, width: "68%", borderRadius: 5, backgroundColor: colors.surfaceAlt },
  lineShort: { height: 10, width: "45%", borderRadius: 5, backgroundColor: colors.surfaceAlt },
});
