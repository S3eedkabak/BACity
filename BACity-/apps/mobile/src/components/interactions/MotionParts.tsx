import { useEffect, useRef, useState } from "react";
import { StyleProp, TextStyle, View } from "react-native";
import Svg, { Path } from "react-native-svg";
import Animated, {
  cancelAnimation,
  Easing,
  useAnimatedProps,
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withTiming,
} from "react-native-reanimated";
import { motion } from "../../navigation/motion";
import { useMotionPreference } from "./useMotionPreference";
const AnimatedPath = Animated.createAnimatedComponent(Path);
export function DrawCheck({
  visible,
  color,
  size = 20,
  delay = 50,
  duration = motion.check,
}: {
  visible: boolean;
  color: string;
  size?: number;
  delay?: number;
  duration?: number;
}) {
  const reduced = useMotionPreference();
  const progress = useSharedValue(reduced && visible ? 1 : 0);
  useEffect(() => {
    progress.value = reduced
      ? Number(visible)
      : withDelay(
          visible ? delay : 0,
          withTiming(Number(visible), {
            duration: visible ? duration : motion.icon,
          }),
        );
    return () => cancelAnimation(progress);
  }, [visible, reduced, delay, duration, progress]);
  const props = useAnimatedProps(() => ({
    strokeDashoffset: 30 * (1 - progress.value),
    opacity: progress.value,
  }));
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" aria-hidden={true}>
      <AnimatedPath
        d="M5 13l4.5 4.5L19 7"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
        strokeDasharray="30 30"
        animatedProps={props}
      />
    </Svg>
  );
}
export function RollingLabel({
  label,
  style,
  direction = 1,
  duration = motion.label,
  distance = 8,
}: {
  label: string;
  style?: StyleProp<TextStyle>;
  direction?: number;
  duration?: number;
  distance?: number;
}) {
  const reduced = useMotionPreference();
  const previous = useRef(label);
  const [outgoing, setOutgoing] = useState<string | null>(null);
  const progress = useSharedValue(1);
  useEffect(() => {
    if (label === previous.current) return;
    setOutgoing(previous.current);
    previous.current = label;
    progress.value = reduced ? 1 : 0;
    if (!reduced) progress.value = withTiming(1, { duration });
    return () => cancelAnimation(progress);
  }, [label, reduced, progress, duration]);
  const enter = useAnimatedStyle(() => ({
    opacity: progress.value,
    transform: [
      { translateY: reduced ? 0 : (1 - progress.value) * direction * distance },
    ],
  }));
  const exit = useAnimatedStyle(() => ({
    position: "absolute",
    opacity: 1 - progress.value,
    transform: [
      { translateY: reduced ? 0 : -progress.value * direction * distance },
    ],
  }));
  return (
    <View
      accessible={false}
      aria-hidden
      accessibilityElementsHidden
      style={{
        overflow: "hidden",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {outgoing && (
        <Animated.Text style={[style, exit]}>{outgoing}</Animated.Text>
      )}
      <Animated.Text style={[style, enter]}>{label}</Animated.Text>
    </View>
  );
}
export function Burst({
  trigger,
  color,
  size = 48,
  particles = 8,
}: {
  trigger: number;
  color: string;
  size?: number;
  particles?: number;
}) {
  const reduced = useMotionPreference();
  const progress = useSharedValue(1);
  useEffect(() => {
    if (!trigger || reduced) {
      progress.value = 1;
      return;
    }
    progress.value = 0;
    progress.value = withTiming(1, {
      duration: motion.burst,
      easing: Easing.out(Easing.cubic),
    });
    return () => cancelAnimation(progress);
  }, [trigger, reduced, progress]);
  const ring = useAnimatedStyle(() => ({
    opacity: reduced ? 0 : Math.max(0, 1 - progress.value * 1.8),
    transform: [{ scale: 0.4 + progress.value * 1.1 }],
  }));
  return (
    <View
      pointerEvents="none"
      accessible={false}
      aria-hidden
      style={{
        position: "absolute",
        width: size,
        height: size,
        left: (48 - size) / 2,
        top: (48 - size) / 2,
      }}
    >
      <Animated.View
        style={[
          {
            position: "absolute",
            top: 2,
            right: 2,
            bottom: 2,
            left: 2,
            borderRadius: size / 2,
            borderWidth: 1.5,
            borderColor: color,
          },
          ring,
        ]}
      />
      {Array.from({ length: particles }, (_, index) => (
        <Particle
          key={index}
          index={index}
          total={particles}
          progress={progress}
          color={color}
          size={size}
          reduced={reduced}
        />
      ))}
    </View>
  );
}
function Particle({
  index,
  total,
  progress,
  color,
  size,
  reduced,
}: {
  index: number;
  total: number;
  progress: { value: number };
  color: string;
  size: number;
  reduced: boolean;
}) {
  const angle = (index / total) * Math.PI * 2 - Math.PI / 2;
  const style = useAnimatedStyle(() => ({
    opacity: reduced ? 0 : 1 - progress.value,
    transform: [
      { translateX: Math.cos(angle) * progress.value * size * 0.65 },
      { translateY: Math.sin(angle) * progress.value * size * 0.65 },
      {
        scale:
          progress.value < 0.2 ? progress.value * 5 : 1 - progress.value * 0.6,
      },
    ],
  }));
  return (
    <Animated.View
      style={[
        {
          position: "absolute",
          left: size / 2 - 1.5,
          top: size / 2 - 1.5,
          width: 3,
          height: 3,
          borderRadius: 2,
          backgroundColor: color,
        },
        style,
      ]}
    />
  );
}
