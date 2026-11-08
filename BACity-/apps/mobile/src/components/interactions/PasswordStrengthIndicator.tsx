import { useEffect, useState } from "react";
import { Text, View } from "react-native";
import Animated, {
  cancelAnimation,
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withSpring,
} from "react-native-reanimated";
import { passwordGuidance } from "../../interactions/policy";
import { colors } from "../../theme/colors";
import { tokens } from "../../theme/tokens";
import { useThemeRevision } from "../../theme/appearance";
import { useMotionPreference } from "./useMotionPreference";
import { DrawCheck, RollingLabel } from "./MotionParts";
function StrengthSegment({
  filled,
  index,
  color,
  reduced,
}: {
  filled: boolean;
  index: number;
  color: string;
  reduced: boolean;
}) {
  const progress = useSharedValue(0);
  useEffect(() => {
    progress.value = reduced
      ? Number(filled)
      : withDelay(
          index * 60,
          withSpring(Number(filled), {
            stiffness: 500,
            damping: 32,
            overshootClamping: true,
          }),
        );
    return () => cancelAnimation(progress);
  }, [filled, reduced, index, progress]);
  const fill = useAnimatedStyle(() => ({ width: `${progress.value * 100}%` }));
  return (
    <View
      style={{
        flex: 1,
        height: 4,
        borderRadius: 2,
        backgroundColor: colors.border,
        overflow: "hidden",
      }}
    >
      <Animated.View style={[{ height: 4, backgroundColor: color }, fill]} />
    </View>
  );
}
export function PasswordStrengthIndicator({ password }: { password: string }) {
  useThemeRevision();
  const reduced = useMotionPreference();
  const guidance = passwordGuidance(password);
  const [estimate, setEstimate] = useState<{
    input: string;
    score: number;
  } | null>(null);
  useEffect(() => {
    if (!password) {
      setEstimate(null);
      return;
    }
    const timer = setTimeout(() => {
      // Bound combinatorial work while typing; long passwords receive a conservative prefix estimate.
      const zxcvbn = require("zxcvbn") as typeof import("zxcvbn");
      const score = zxcvbn(password.slice(0, 32)).score;
      setEstimate({ input: password, score });
    }, 120);
    return () => clearTimeout(timer);
  }, [password]);
  // A stale estimate is never shown for a newly typed password. Only score is rendered; no password leaves this component.
  const score = estimate?.input === password ? estimate.score : null;
  const level =
    !password || !guidance.valid ? 0 : score === null ? 0 : Math.max(1, score);
  const label = !password
    ? "Password strength"
    : !guidance.valid
      ? "Does not meet policy"
      : score === null
        ? "Checking strength…"
        : ["Very weak", "Weak", "Fair", "Good", "Strong"][score];
  const color =
    level < 2 ? colors.danger : level < 3 ? colors.primaryDark : colors.free;
  return (
    <View style={{ gap: 8 }}>
      <View accessible={false} style={{ flexDirection: "row", gap: 4 }}>
        {[1, 2, 3, 4].map((index) => (
          <StrengthSegment
            key={index}
            index={index - 1}
            filled={index <= level}
            color={color}
            reduced={reduced}
          />
        ))}
      </View>
      <View
        accessibilityLiveRegion="polite"
        accessible
        accessibilityLabel={`${label}. ${guidance.text}`}
        style={{ alignItems: "flex-start", gap: 4 }}
      >
        <RollingLabel label={label} style={{ ...tokens.type.caption, color }} />
        <Text style={{ ...tokens.type.caption, color: colors.textMuted }}>
          {guidance.text}
        </Text>
      </View>
      <View style={{ flexDirection: "row", gap: 8, alignItems: "center" }}>
        <View style={{ width: 16, height: 16 }}>
          <DrawCheck
            duration={200}
            delay={0}
            visible={guidance.valid}
            color={colors.free}
            size={16}
          />
        </View>
        <Text style={{ ...tokens.type.caption, color: colors.textMuted }}>
          8+ characters · not only spaces · at most 4,096 UTF-8 bytes
        </Text>
      </View>
      <Text style={{ ...tokens.type.caption, color: colors.textMuted }}>
        Estimated locally. Use a unique password; this is not a breach check.
      </Text>
    </View>
  );
}
