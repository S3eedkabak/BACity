import { useEffect, useRef, useState } from "react";
import {
  AccessibilityInfo,
  Animated,
  Easing,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { colors } from "../theme/colors";
import { fonts } from "../theme/fonts";

export function AppLoadingScreen() {
  const logoOpacity = useRef(new Animated.Value(0)).current;
  const logoScale = useRef(new Animated.Value(0.88)).current;
  const blobOne = useRef(new Animated.Value(0)).current;
  const blobTwo = useRef(new Animated.Value(0)).current;
  const progress = useRef(new Animated.Value(0)).current;
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    let mounted = true;

    AccessibilityInfo.isReduceMotionEnabled().then((enabled) => {
      if (mounted) setReducedMotion(enabled);
    });

    const subscription = AccessibilityInfo.addEventListener(
      "reduceMotionChanged",
      setReducedMotion
    );

    return () => {
      mounted = false;
      subscription.remove();
    };
  }, []);

  useEffect(() => {
    if (reducedMotion) {
      logoOpacity.setValue(1);
      logoScale.setValue(1);
      progress.setValue(1);
      return;
    }

    Animated.parallel([
      Animated.timing(logoOpacity, {
        toValue: 1,
        duration: 650,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: true,
      }),
      Animated.spring(logoScale, {
        toValue: 1,
        damping: 14,
        stiffness: 120,
        mass: 0.8,
        useNativeDriver: true,
      }),
      Animated.timing(progress, {
        toValue: 1,
        duration: 1400,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: false,
      }),
    ]).start();

    const loopOne = Animated.loop(
      Animated.sequence([
        Animated.timing(blobOne, {
          toValue: 1,
          duration: 3200,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
        Animated.timing(blobOne, {
          toValue: 0,
          duration: 3200,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
      ])
    );

    const loopTwo = Animated.loop(
      Animated.sequence([
        Animated.timing(blobTwo, {
          toValue: 1,
          duration: 3800,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
        Animated.timing(blobTwo, {
          toValue: 0,
          duration: 3800,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
      ])
    );

    loopOne.start();
    loopTwo.start();

    return () => {
      loopOne.stop();
      loopTwo.stop();
    };
  }, [blobOne, blobTwo, logoOpacity, logoScale, progress, reducedMotion]);

  const progressWidth = progress.interpolate({
    inputRange: [0, 1],
    outputRange: ["0%", "100%"],
  });

  return (
    <View style={styles.container}>
      <Animated.View
        style={[
          styles.blob,
          styles.blobOne,
          {
            transform: [
              {
                translateX: blobOne.interpolate({
                  inputRange: [0, 1],
                  outputRange: [0, 22],
                }),
              },
              {
                translateY: blobOne.interpolate({
                  inputRange: [0, 1],
                  outputRange: [0, 18],
                }),
              },
              {
                scale: blobOne.interpolate({
                  inputRange: [0, 1],
                  outputRange: [1, 1.08],
                }),
              },
            ],
          },
        ]}
      />
      <Animated.View
        style={[
          styles.blob,
          styles.blobTwo,
          {
            transform: [
              {
                translateX: blobTwo.interpolate({
                  inputRange: [0, 1],
                  outputRange: [0, -18],
                }),
              },
              {
                translateY: blobTwo.interpolate({
                  inputRange: [0, 1],
                  outputRange: [0, 24],
                }),
              },
              {
                scale: blobTwo.interpolate({
                  inputRange: [0, 1],
                  outputRange: [1, 0.92],
                }),
              },
            ],
          },
        ]}
      />
      <View style={styles.blobThree} />

      <Animated.View
        style={[
          styles.content,
          {
            opacity: logoOpacity,
            transform: [{ scale: logoScale }],
          },
        ]}
      >
        <View style={styles.brandRow}>
          <Text style={styles.brand}>BAcity</Text>
          <View style={styles.brandDot} />
        </View>

        <Text style={styles.status}>
          Finding something worth going out for…
        </Text>

        <View style={styles.track}>
          <Animated.View style={[styles.progress, { width: progressWidth }]} />
        </View>

        <Text style={styles.motionNote}>
          {reducedMotion
            ? "Ready when you are."
            : "Good things are worth the wait."}
        </Text>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    overflow: "hidden",
    alignItems: "center",
    justifyContent: "center",
  },
  blob: {
    position: "absolute",
    borderRadius: 999,
  },
  blobOne: {
    width: 220,
    height: 220,
    left: -45,
    top: 70,
    backgroundColor: colors.primary,
    opacity: 0.9,
  },
  blobTwo: {
    width: 150,
    height: 150,
    right: -35,
    top: 135,
    backgroundColor: colors.accent,
    opacity: 0.78,
  },
  blobThree: {
    position: "absolute",
    width: 280,
    height: 155,
    left: "50%",
    bottom: -70,
    marginLeft: -140,
    borderRadius: 999,
    backgroundColor: colors.primarySoft,
  },
  content: {
    width: "100%",
    paddingHorizontal: 61,
    alignItems: "center",
  },
  brandRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  brand: {
    color: colors.text,
    fontFamily: fonts.black,
    fontSize: 52,
    letterSpacing: -2,
  },
  brandDot: {
    width: 14,
    height: 14,
    borderRadius: 7,
    backgroundColor: colors.primary,
    marginLeft: 8,
    marginTop: 18,
  },
  status: {
    color: colors.textMuted,
    fontFamily: fonts.medium,
    fontSize: 15,
    textAlign: "center",
    marginTop: 40,
  },
  track: {
    width: "100%",
    height: 8,
    borderRadius: 4,
    overflow: "hidden",
    backgroundColor: colors.primarySoft,
    marginTop: 38,
  },
  progress: {
    height: "100%",
    borderRadius: 4,
    backgroundColor: colors.primary,
  },
  motionNote: {
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 12,
    textAlign: "center",
    marginTop: 16,
  },
});
