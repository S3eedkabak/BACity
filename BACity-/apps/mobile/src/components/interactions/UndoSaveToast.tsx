import { Text, View } from "react-native";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToggleSaveEvent } from "../../hooks/useEvents";
import type { EventOut } from "../../types/event";
import { MorphActionButton } from "./ActionButton";
import { colors } from "../../theme/colors";
import { tokens } from "../../theme/tokens";
import { useThemeRevision } from "../../theme/appearance";
export function UndoSaveToast() {
  useThemeRevision();
  const client = useQueryClient();
  const mutation = useToggleSaveEvent();
  const removed = useQuery<EventOut | null>({
    queryKey: ["saved-undo"],
    queryFn: () => null,
    enabled: false,
    initialData: null,
  });
  if (!removed.data) return null;
  const event = removed.data;
  return (
    <View
      style={{
        gap: 8,
        backgroundColor: colors.surfaceAlt,
        padding: 16,
        borderRadius: 20,
        marginHorizontal: 20,
        marginBottom: 12,
      }}
    >
      <Text
        accessibilityLiveRegion="polite"
        style={{ ...tokens.type.metadata, color: colors.text }}
      >
        Removed {event.title} from saved events.
      </Text>
      {mutation.isError && (
        <Text
          accessibilityRole="alert"
          style={{ ...tokens.type.caption, color: colors.danger }}
        >
          {mutation.error.message}
        </Text>
      )}
      <View style={{ flexDirection: "row", gap: 8 }}>
        <View style={{ flex: 1 }}>
          <MorphActionButton
            title="Undo"
            state={
              mutation.isPending
                ? "loading"
                : mutation.isError
                  ? "error"
                  : "idle"
            }
            onPress={() =>
              mutation.mutate(
                { id: event.id, saved: false, event, desiredSaved: true },
                {
                  onSuccess: () => {
                    if (
                      client.getQueryData<EventOut>(["saved-undo"])?.id ===
                      event.id
                    )
                      client.setQueryData(["saved-undo"], null);
                  },
                },
              )
            }
          />
        </View>
        <MorphActionButton
          title="Dismiss"
          variant="secondary"
          onPress={() => client.setQueryData(["saved-undo"], null)}
        />
      </View>
    </View>
  );
}
