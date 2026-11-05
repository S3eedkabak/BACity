import { useThemeRevision } from "../../theme/appearance";
import { Alert, Platform, Text, View } from "react-native";
import { useIsMutating } from "@tanstack/react-query";
import { router } from "expo-router";
import { useAuthStore } from "../../store/authStore";
import { useSavedEvents, useToggleSaveEvent } from "../../hooks/useEvents";
import type { EventOut } from "../../types/event";
import { LikeAction } from "./LikeAction";
import { MorphActionButton } from "./ActionButton";
import { colors } from "../../theme/colors";
import { tokens } from "../../theme/tokens";
export function SaveEventAction({
  event,
  expanded = false,
}: {
  event: EventOut;
  expanded?: boolean;
}) {
  useThemeRevision();
  const token = useAuthStore((s) => s.token);
  const library = useSavedEvents();
  const save = useToggleSaveEvent();
  const saved = !!library.data?.some((item) => item.id === event.id);
  const busy =
    useIsMutating({
      mutationKey: ["save-event"],
      predicate: (value) =>
        (value.state.variables as { id?: string })?.id === event.id,
    }) > 0;
  function toggle() {
    if (!token) {
      router.push("/auth");
      return;
    }
    if (!library.data) {
      void library.refetch();
      return;
    }
    save.mutate(
      { id: event.id, saved, event },
      {
        onError: (error) => {
          if (!expanded && Platform.OS !== "web")
            Alert.alert("Could not update saved event", error.message);
        },
      },
    );
  }
  const disabled = !!token && library.isPending;
  if (!expanded)
    return (
      <View>
        <LikeAction
          active={saved}
          busy={busy || (!!token && library.isPending)}
          disabled={disabled}
          label={
            library.isError
              ? `Reload saved status for ${event.title}`
              : saved
                ? `Remove ${event.title} from saved events`
                : `Save ${event.title}`
          }
          onPress={toggle}
        />
        {save.isError && Platform.OS === "web" && (
          <Text
            accessibilityRole="alert"
            style={{ color: colors.danger, maxWidth: 160 }}
          >
            {save.error.message}
          </Text>
        )}
      </View>
    );
  return (
    <View style={{ gap: 8, paddingHorizontal: 20 }}>
      <MorphActionButton
        title={saved ? "Saved · Remove from plans" : "Save this event"}
        icon={saved ? "bookmark" : "bookmark-outline"}
        variant={saved ? "secondary" : "primary"}
        state={busy ? "loading" : save.isError ? "error" : "idle"}
        disabled={disabled}
        onPress={toggle}
      />
      {(save.isError || library.isError) && (
        <>
          <Text
            accessibilityRole="alert"
            style={{ ...tokens.type.metadata, color: colors.danger }}
          >
            {save.error?.message ?? library.error?.message}
          </Text>
          {library.isError && (
            <MorphActionButton
              title="Reload saved events"
              variant="secondary"
              onPress={() => void library.refetch()}
            />
          )}
        </>
      )}
    </View>
  );
}
