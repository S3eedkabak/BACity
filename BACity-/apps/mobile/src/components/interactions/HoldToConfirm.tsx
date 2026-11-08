import { useThemeRevision } from "../../theme/appearance";
import { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  AppState,
  Modal,
  Pressable,
  Text,
  View,
} from "react-native";
import Animated, {
  cancelAnimation,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
  withSpring,
  useAnimatedProps,
} from "react-native-reanimated";
import Svg, { Circle } from "react-native-svg";
import { DrawCheck, RollingLabel } from "./MotionParts";
import { motion } from "../../navigation/motion";
const ProgressCircle = Animated.createAnimatedComponent(Circle);
import { useIsFocused } from "@react-navigation/native";
import { colors } from "../../theme/colors";
import { tokens } from "../../theme/tokens";
import { MorphActionButton } from "./ActionButton";
import { useMotionPreference } from "./useMotionPreference";
import { successHaptic } from "./haptics";
import type { ActionState } from "../../interactions/policy";

export function HoldToConfirm({
  title,
  description,
  onConfirm,
  disabled = false,
}: {
  title: string;
  description: string;
  onConfirm: () => Promise<void>;
  disabled?: boolean;
}) {
  useThemeRevision();
  const reduced = useMotionPreference();
  const focused = useIsFocused();
  const [state, setState] = useState<ActionState>("idle");
  const [error, setError] = useState("");
  const [dialog, setDialog] = useState(false);
  const origin = useRef({ x: 0, y: 0 });
  const held = useRef(false);
  const locked = useRef(false);
  const mounted = useRef(true);
  const progress = useSharedValue(0);
  const cancel = () => {
    held.current = false;
    cancelAnimation(progress);
    progress.value = reduced
      ? 0
      : withSpring(0, { stiffness: 300, damping: 30 });
  };
  useEffect(() => {
    mounted.current = true;
    const listener = AppState.addEventListener("change", (status) => {
      if (status !== "active") {
        cancel();
        setDialog(false);
      }
    });
    return () => {
      mounted.current = false;
      cancel();
      listener.remove();
    };
  }, []);
  useEffect(() => {
    if (!focused || disabled || reduced) cancel();
  }, [focused, disabled, reduced]);
  async function confirm() {
    if (locked.current || disabled || !focused) return;
    locked.current = true;
    cancel();
    setDialog(false);
    setState("loading");
    setError("");
    try {
      await onConfirm();
      if (mounted.current) {
        setState("success");
        successHaptic(reduced);
      }
    } catch (failure: any) {
      if (mounted.current) {
        setState("error");
        setError(
          failure?.message ?? "Could not complete this action. Try again.",
        );
      }
      locked.current = false;
    }
  }
  const ring = useAnimatedProps(() => ({
    strokeDashoffset: 88 * (1 - progress.value),
  }));
  const press = useAnimatedStyle(() => ({
    transform: [{ scale: reduced ? 1 : 1 - progress.value * 0.03 }],
  }));
  const unavailable = disabled || state === "loading" || state === "success";
  return (
    <View style={{ gap: 12 }}>
      <Text style={{ ...tokens.type.metadata, color: colors.textMuted }}>
        {description}
      </Text>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`Hold for 1.2 seconds to ${title.toLowerCase()}`}
        accessibilityHint="Alternatively use Confirm another way below."
        accessibilityState={{
          disabled: unavailable,
          busy: state === "loading",
        }}
        disabled={unavailable}
        delayLongPress={tokens.motion.hold}
        onPressIn={(event) => {
          if (locked.current) return;
          origin.current = {
            x: event.nativeEvent.pageX,
            y: event.nativeEvent.pageY,
          };
          held.current = true;
          progress.value = reduced
            ? 0
            : withTiming(1, { duration: tokens.motion.hold });
        }}
        onPressOut={cancel}
        onTouchCancel={cancel}
        onTouchMove={(event) => {
          if (
            Math.hypot(
              event.nativeEvent.pageX - origin.current.x,
              event.nativeEvent.pageY - origin.current.y,
            ) > 12
          )
            cancel();
        }}
        onLongPress={() => {
          if (held.current) void confirm();
        }}
        style={{
          minHeight: 56,
          padding: 16,
          backgroundColor:
            state === "success" ? colors.successSurface : colors.dangerSurface,
          borderRadius: 26,
          overflow: "hidden",
          justifyContent: "center",
        }}
      >
        <Animated.View
          pointerEvents="none"
          style={[
            {
              flexDirection: "row",
              gap: 12,
              alignItems: "center",
              justifyContent: "center",
            },
            press,
          ]}
        >
          <View
            style={{
              width: 36,
              height: 36,
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {state === "success" ? (
              <DrawCheck visible color={colors.free} duration={250} />
            ) : state === "loading" ? (
              <ActivityIndicator color={colors.danger} />
            ) : (
              <Svg width={36} height={36} viewBox="0 0 36 36">
                <Circle
                  cx={18}
                  cy={18}
                  r={14}
                  stroke={colors.border}
                  strokeWidth={2}
                  fill="none"
                />
                <ProgressCircle
                  cx={18}
                  cy={18}
                  r={14}
                  stroke={colors.danger}
                  strokeWidth={2}
                  fill="none"
                  strokeDasharray="88 88"
                  strokeLinecap="round"
                  rotation={-90}
                  origin="18,18"
                  animatedProps={ring}
                />
              </Svg>
            )}
          </View>
          <View style={{ flex: 1 }}>
            <RollingLabel
              label={
                state === "loading"
                  ? "Working…"
                  : state === "success"
                    ? "Completed"
                    : `Hold to ${title.toLowerCase()}`
              }
              style={{
                ...tokens.type.action,
                textAlign: "center",
                color: state === "success" ? colors.free : colors.danger,
              }}
            />
          </View>
        </Animated.View>
      </Pressable>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Confirm another way"
        disabled={unavailable}
        onPress={() => setDialog(true)}
        style={{
          minHeight: 48,
          justifyContent: "center",
          alignItems: "center",
        }}
      >
        <Text style={{ ...tokens.type.action, color: colors.primaryDark }}>
          Confirm another way
        </Text>
      </Pressable>
      {!!error && (
        <Text
          accessibilityRole="alert"
          style={{ ...tokens.type.metadata, color: colors.danger }}
        >
          {error}
        </Text>
      )}
      <Modal
        visible={dialog && focused}
        transparent
        animationType="none"
        onRequestClose={() => setDialog(false)}
      >
        <View
          style={{
            flex: 1,
            padding: 24,
            backgroundColor: colors.overlay,
            justifyContent: "center",
          }}
        >
          <View
            accessibilityViewIsModal
            style={{
              backgroundColor: colors.surface,
              borderRadius: 24,
              padding: 24,
              gap: 16,
            }}
          >
            <Text
              accessibilityRole="header"
              style={{ ...tokens.type.section, color: colors.text }}
            >
              {title}?
            </Text>
            <Text style={{ ...tokens.type.body, color: colors.text }}>
              {description}
            </Text>
            <MorphActionButton
              variant="secondary"
              title="Cancel"
              onPress={() => setDialog(false)}
            />
            <MorphActionButton
              variant="danger"
              title={title}
              onPress={() => void confirm()}
            />
          </View>
        </View>
      </Modal>
    </View>
  );
}
