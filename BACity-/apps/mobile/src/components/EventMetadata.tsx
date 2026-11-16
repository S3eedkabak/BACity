import { Text, View } from "react-native";
import { themedStyles, useThemeRevision } from "../theme/appearance";
import { colors } from "../theme/colors";
import { tokens } from "../theme/tokens";
import type { EventOut } from "../types/event";

export function eventPriceLabel(event: Pick<EventOut, "price" | "currency">) {
  return event.price === 0
    ? "Free"
    : event.price == null
      ? "Price unknown"
      : `${event.price} ${event.currency || "EUR"}`;
}

/** Content semantics shared by list and featured cards; feature actions keep their own owners. */
export function EventMetadata({ event }: { event: EventOut }) {
  useThemeRevision();
  return (
    <View style={styles.row}>
      <Text style={styles.category}>{event.category}</Text>
      <Text style={[styles.price, event.price === 0 && { color: colors.free }]}>
        {eventPriceLabel(event)}
      </Text>
    </View>
  );
}
const styles = themedStyles(() => ({
  row: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: tokens.space.sm,
    alignItems: "center",
  },
  category: { ...tokens.type.caption, color: colors.textMuted },
  price: { ...tokens.type.caption, color: colors.textMuted },
}));
