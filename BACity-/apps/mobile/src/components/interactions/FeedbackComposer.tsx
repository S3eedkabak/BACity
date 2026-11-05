import { ReactionFace } from "./ReactionFace";
import { AnimatedPressable } from "../motion/Motion";
import { useThemeRevision } from "../../theme/appearance";
import { useEffect, useRef, useState } from "react";
import { Text, View } from "react-native";
import Animated, {
  cancelAnimation,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
  LinearTransition,
} from "react-native-reanimated";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { publishReview, type Review } from "../../api/interactions";
import { reviewDimensions, reviewError } from "../../interactions/policy";
import { AppTextField } from "./AppTextField";
import { MorphActionButton } from "./ActionButton";
import { StarRating } from "./StarRating";
import { colors } from "../../theme/colors";
import { tokens } from "../../theme/tokens";
import { Disclosure } from "../CommunityUI";
import { useMotionPreference } from "./useMotionPreference";
import { successHaptic } from "./haptics";

export function FeedbackComposer({
  id,
  kind,
  ownReview,
}: {
  id: string;
  kind: "event" | "place";
  ownReview?: Review;
}) {
  useThemeRevision();
  const [expanded, setExpanded] = useState(false);
  const [body, setBody] = useState("");
  const [ratings, setRatings] = useState<Record<string, number>>({});
  const [validation, setValidation] = useState("");
  const lock = useRef(false);
  const client = useQueryClient();
  const reduced = useMotionPreference();
  const mutation = useMutation({
    mutationFn: () => publishReview(kind, id, body.trim(), ratings),
    onSuccess: async () => {
      successHaptic(reduced);
      await Promise.all([
        client.invalidateQueries({ queryKey: ["reviews", kind, id] }),
        client.invalidateQueries({ queryKey: ["review-summary", kind, id] }),
        client.invalidateQueries({ queryKey: ["profile"] }),
      ]);
    },
  });
  function open(rating?: number) {
    setBody(ownReview?.body ?? "");
    setRatings(
      { ...ownReview?.dimensions,
        ...(rating ? { [kind === "event" ? "worth_attending" : "atmosphere"]: rating } : {}) },
    );
    setValidation("");
    mutation.reset();
    setExpanded(true);
  }
  async function submit() {
    if (lock.current) return;
    const error = reviewError(kind, body, ratings);
    setValidation(error);
    if (error) return;
    lock.current = true;
    try {
      await mutation.mutateAsync();
    } catch {
      /* Keep draft and render mutation error. */
    } finally {
      lock.current = false;
    }
  }
  const shape = useSharedValue(0);
  useEffect(() => {
    shape.value = withTiming(expanded ? 1 : 0, { duration: reduced ? 0 : 300 });
    return () => cancelAnimation(shape);
  }, [expanded, reduced, shape]);
  const surface = useAnimatedStyle(() => ({
    borderRadius: 32 - shape.value * 24,
    padding: 16 + shape.value * 4,
  }));
  const reactions = [
    { label: "Loved it", rating: 5 },
    { label: "Enjoyed it", rating: 4 },
    { label: "Could be better", rating: 2 },
    { label: "Disappointed", rating: 1 },
  ];
  const primary = kind === "event" ? "worth_attending" : "atmosphere";
  const reactionRow = (
    <View
      style={{ flexDirection: "row", alignItems: "center", flexWrap: "wrap" }}
    >
      <Text
        style={{
          ...tokens.type.metadata,
          color: colors.text,
          flexGrow: 1,
          marginRight: 8,
        }}
      >
        How was it?
      </Text>
      {reactions.map((reaction) => (
        <AnimatedPressable
          key={reaction.rating}
          accessibilityRole="button"
          accessibilityLabel={reaction.label}
          accessibilityState={{
            selected: expanded && ratings[primary] === reaction.rating,
            disabled: mutation.isPending,
          }}
          disabled={mutation.isPending}
          onPress={() => {
            if (!expanded) open(reaction.rating);
            else if (ratings[primary] === reaction.rating) setExpanded(false);
            else
              setRatings((current) => ({
                ...current,
                [primary]: reaction.rating,
              }));
          }}
          style={{
            width: 48,
            height: 48,
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <ReactionFace
            rating={reaction.rating}
            color={
              expanded && ratings[primary] === reaction.rating
                ? reaction.rating >= 4
                  ? colors.free
                  : colors.danger
                : colors.textMuted
            }
          />
        </AnimatedPressable>
      ))}
    </View>
  );
  if (!expanded)
    return (
      <Animated.View
        layout={reduced ? undefined : LinearTransition.duration(300)}
        style={[
          { gap: 4, backgroundColor: colors.surface, overflow: "hidden" },
          surface,
        ]}
      >
        {reactionRow}
        {ownReview && (
          <MorphActionButton
            title="Edit your review"
            variant="secondary"
            onPress={() => open()}
          />
        )}
        <Text style={{ ...tokens.type.caption, color: colors.textMuted }}>
          Public {kind} review
        </Text>
      </Animated.View>
    );
  return (
    <Animated.View
      layout={reduced ? undefined : LinearTransition.duration(300)}
      style={[
        { gap: 16, backgroundColor: colors.surface, overflow: "hidden" },
        surface,
      ]}
    >
      {reactionRow}
      <Text
        accessibilityRole="header"
        style={{ ...tokens.type.section, color: colors.text }}
      >
        How was your experience?
      </Text>
      <Text style={{ ...tokens.type.metadata, color: colors.textMuted }}>
        This is a public {kind} review. For private account or support requests,
        use Privacy & account rights in your profile. Event reviews open after
        the event.
      </Text>
      {mutation.isSuccess ? (
        <>
          <Text
            accessibilityRole="alert"
            style={{ ...tokens.type.body, color: colors.free }}
          >
            Your review was published.
          </Text>
          <MorphActionButton
            title="Publish review"
            state="success"
            successLabel="Review published"
            onPress={() => setExpanded(false)}
          />
          <MorphActionButton
            title="Done"
            variant="secondary"
            onPress={() => setExpanded(false)}
          />
        </>
      ) : (
        <>
          <StarRating
            value={ratings[primary] ?? 0}
            label={kind === "event" ? "Worth attending" : "Atmosphere"}
            disabled={mutation.isPending}
            onChange={(value) =>
              setRatings((current) => ({ ...current, [primary]: value }))
            }
          />
          <AppTextField
            label="Your review"
            value={body}
            onChangeText={setBody}
            multiline
            maxLength={3000}
            editable={!mutation.isPending}
            error={
              validation && body.trim().length < 10 ? validation : undefined
            }
          />
          <Disclosure title="Rate more aspects (optional)" icon="star-outline">
            {reviewDimensions[kind]
              .filter((key) => key !== primary)
              .map((key) => (
                <StarRating
                  key={key}
                  value={ratings[key] ?? 0}
                  label={key.replaceAll("_", " ")}
                  disabled={mutation.isPending}
                  onChange={(value) =>
                    setRatings((current) => ({ ...current, [key]: value }))
                  }
                />
              ))}
          </Disclosure>
          {!!validation && (
            <Text
              accessibilityRole="alert"
              style={{ ...tokens.type.caption, color: colors.danger }}
            >
              {validation}
            </Text>
          )}
          {mutation.isError && (
            <Text
              accessibilityRole="alert"
              style={{ ...tokens.type.metadata, color: colors.danger }}
            >
              {mutation.error.message}
            </Text>
          )}
          <MorphActionButton
            title={ownReview ? "Update review" : "Publish review"}
            state={
              mutation.isPending
                ? "loading"
                : mutation.isError
                  ? "error"
                  : "idle"
            }
            onPress={() => void submit()}
          />
          <MorphActionButton
            title="Cancel"
            variant="secondary"
            disabled={mutation.isPending}
            onPress={() => setExpanded(false)}
          />
        </>
      )}
    </Animated.View>
  );
}
