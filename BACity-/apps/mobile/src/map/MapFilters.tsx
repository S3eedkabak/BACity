import { useState } from "react";
import { Pressable, Switch, Text, View } from "react-native";
import { useThemeRevision } from "../theme/appearance";
import { AppIcon } from "../components/AppIcon";
import { MorphActionButton } from "../components/interactions/ActionButton";
import { SegmentedControl } from "../components/interactions/SegmentedControl";
import { AppTextField } from "../components/interactions/AppTextField";
import { DateField } from "../components/filters/DateField";
import { colors } from "../theme/colors";
import { tokens } from "../theme/tokens";
import { dateRange, presetRange, type MapFilters as Filters } from "./area";
const categories = [
  "Music",
  "Culture",
  "Nightlife",
  "Food & Drink",
  "Markets",
  "Workshops",
  "Family",
  "Arts",
  "Theatre",
  "Sports",
  "Education",
  "Community",
  "Networking",
  "Festivals",
  "Student",
  "Technology",
  "Comedy",
  "Exhibitions",
  "Other",
];
const day = (value?: string) => {
  if (!value) return "";
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Bratislava",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date(value));
  return ["year", "month", "day"]
    .map((type) => parts.find((part) => part.type === type)?.value)
    .join("-");
};
export function MapFilters({
  value,
  onChange,
  onDone,
  simple = false,
}: {
  value: Filters;
  onChange: (value: Filters) => void;
  onDone?: () => void;
  simple?: boolean;
}) {
  useThemeRevision();
  const [draft, setDraft] = useState(value),
    [preset, setPreset] = useState(value.starts_after ? "custom" : "all"),
    [custom, setCustom] = useState(!!value.starts_after),
    [from, setFrom] = useState(day(value.starts_after)),
    [to, setTo] = useState(day(value.starts_before)),
    [error, setError] = useState(""),
    [query, setQuery] = useState(""),
    [choosing, setChoosing] = useState(false);
  function apply() {
    const range = custom ? dateRange(from, to) : {};
    if (!range) {
      setError("Choose a start and end date in order.");
      return;
    }
    onChange({ ...draft, ...range });
    onDone?.();
  }
  return (
    <View style={{ gap: 16 }}>
      {!simple && (
        <>
          <Text style={{ ...tokens.type.action, color: colors.text }}>
            When
          </Text>
          <SegmentedControl
            label="Event dates"
            options={[
              { id: "all", label: "Any time" },
              ...["Today", "Tomorrow", "Weekend"].map((id) => ({
                id,
                label: id,
              })),
              { id: "custom", label: "Dates…" },
            ]}
            value={preset}
            onChange={(id) => {
              setPreset(id);
              setCustom(id === "custom");
              setError("");
              if (id !== "custom")
                setDraft({
                  ...draft,
                  ...(id === "all"
                    ? { starts_after: undefined, starts_before: undefined }
                    : presetRange(id as "Today" | "Tomorrow" | "Weekend")),
                });
            }}
          />
          {custom && (
            <>
              <DateField label="From" value={from} onChange={setFrom} />
              <DateField label="Through" value={to} onChange={setTo} />
              <Text style={{ ...tokens.type.caption, color: colors.textMuted }}>
                Dates use Bratislava time.
              </Text>
            </>
          )}
        </>
      )}
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "space-between",
          minHeight: 48,
        }}
      >
        <Text style={{ ...tokens.type.body, color: colors.text }}>
          Free events only
        </Text>
        <Switch
          accessibilityLabel="Free events only"
          value={!!draft.free_only}
          onValueChange={(free_only) => setDraft({ ...draft, free_only })}
          trackColor={{ true: colors.primary }}
        />
      </View>
      {!simple && (
        <View
          style={{
            flexDirection: "row",
            alignItems: "center",
            justifyContent: "space-between",
            minHeight: 48,
          }}
        >
          <Text style={{ ...tokens.type.body, color: colors.text }}>
            Fresh listings only
          </Text>
          <Switch
            accessibilityLabel="Fresh listings only"
            value={draft.status === "fresh"}
            onValueChange={(fresh) =>
              setDraft({ ...draft, status: fresh ? "fresh" : undefined })
            }
            trackColor={{ true: colors.primary }}
          />
        </View>
      )}
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Choose interest"
        accessibilityState={{ expanded: choosing }}
        onPress={() => setChoosing(!choosing)}
        style={{
          minHeight: 52,
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <Text style={{ ...tokens.type.body, color: colors.text }}>
          Interest
        </Text>
        <Text style={{ ...tokens.type.metadata, color: colors.primaryDark }}>
          {draft.category || "All interests"} ›
        </Text>
      </Pressable>
      {choosing && (
        <>
          <AppTextField
            label="Find an interest"
            placeholder="Search interests"
            value={query}
            onChangeText={setQuery}
          />
          {[
            "All interests",
            ...categories.filter((c) =>
              c.toLowerCase().includes(query.toLowerCase()),
            ),
          ].map((category) => {
            const selected =
              category === "All interests"
                ? !draft.category
                : draft.category === category;
            return (
              <Pressable
                key={category}
                accessibilityRole="radio"
                accessibilityState={{ checked: selected }}
                onPress={() => {
                  setDraft({
                    ...draft,
                    category:
                      category === "All interests" ? undefined : category,
                  });
                  setChoosing(false);
                }}
                style={{
                  minHeight: 48,
                  flexDirection: "row",
                  alignItems: "center",
                  justifyContent: "space-between",
                  borderBottomWidth: 0.5,
                  borderColor: colors.border,
                }}
              >
                <Text
                  style={{
                    ...tokens.type.body,
                    color: selected ? colors.primaryDark : colors.text,
                  }}
                >
                  {category}
                </Text>
                {selected && (
                  <AppIcon
                    name="checkmark"
                    size={18}
                    color={colors.primaryDark}
                  />
                )}
              </Pressable>
            );
          })}
        </>
      )}
      {!!error && (
        <Text accessibilityRole="alert" style={{ color: colors.danger }}>
          {error}
        </Text>
      )}
      <MorphActionButton title="Apply filters" onPress={apply} />
      <Pressable
        accessibilityRole="button"
        onPress={() => {
          setDraft({ q: value.q });
          setPreset("all");
          setCustom(false);
          setFrom("");
          setTo("");
          setError("");
        }}
        style={{ minHeight: 48, justifyContent: "center" }}
      >
        <Text style={{ ...tokens.type.action, color: colors.primaryDark }}>
          Reset filters
        </Text>
      </Pressable>
    </View>
  );
}
export { filterSummary } from "./filterSummary";
