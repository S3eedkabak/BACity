/**
 * Explore screen (spec section 33): free-text search over /events/search,
 * plus category chips that fall back to a filtered /events list when the
 * search box is empty.
 */
import { useState } from "react";
import { FlatList, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useEvents, useSearchEvents } from "../../src/hooks/useEvents";
import { EventCard } from "../../src/components/EventCard";
import { EmptyState } from "../../src/components/EmptyState";
import { LoadingState } from "../../src/components/LoadingState";
import { colors } from "../../src/theme/colors";
import { EventCategory } from "../../src/types/event";

const CATEGORIES: EventCategory[] = [
  "Music", "Nightlife", "Culture", "Theatre", "Student", "Food & Drink", "Markets", "Workshops",
];

export default function ExploreScreen() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<EventCategory | null>(null);

  const searchResult = useSearchEvents(query);
  const listResult = useEvents({ category: category ?? undefined, limit: 50 });

  const isSearching = query.trim().length > 0;
  const { data, isLoading, isError } = isSearching ? searchResult : listResult;
  const items = isSearching ? (data as any[] | undefined) : (data as any)?.items;

  return (
    <View style={styles.container}>
      <View style={styles.searchBar}>
        <Ionicons name="search" size={18} color={colors.textMuted} />
        <TextInput
          style={styles.input}
          placeholder="Search events..."
          placeholderTextColor={colors.textMuted}
          value={query}
          onChangeText={setQuery}
          autoCorrect={false}
        />
      </View>

      {!isSearching && (
        <FlatList
          horizontal
          data={CATEGORIES}
          keyExtractor={(c) => c}
          showsHorizontalScrollIndicator={false}
          style={styles.chipRow}
          contentContainerStyle={{ gap: 8, paddingHorizontal: 16 }}
          renderItem={({ item }) => {
            const active = category === item;
            return (
              <Pressable
                style={[styles.chip, active && styles.chipActive]}
                onPress={() => setCategory(active ? null : item)}
              >
                <Text style={[styles.chipText, active && styles.chipTextActive]}>{item}</Text>
              </Pressable>
            );
          }}
        />
      )}

      {isLoading ? (
        <LoadingState />
      ) : isError ? (
        <EmptyState title="Something went wrong" subtitle="Couldn't reach the API." />
      ) : (
        <FlatList
          data={items ?? []}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.results}
          renderItem={({ item }) => <EventCard event={item} />}
          ListEmptyComponent={
            <EmptyState
              title={isSearching ? "No matches" : "No events in this category yet"}
              subtitle={isSearching ? `Nothing found for "${query}"` : undefined}
            />
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  searchBar: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: colors.surface,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    margin: 16,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  input: { flex: 1, color: colors.text, fontSize: 15 },
  chipRow: { marginBottom: 8, flexGrow: 0 },
  chip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 8,
    backgroundColor: colors.surface,
  },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { color: colors.textMuted, fontSize: 13, fontWeight: "600" },
  chipTextActive: { color: "#fff" },
  results: { padding: 16, paddingBottom: 32 },
});