import { useState } from "react";
import { FlatList, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useEvents, useSearchEvents } from "../../src/hooks/useEvents";
import { EventCard } from "../../src/components/EventCard";
import { EmptyState } from "../../src/components/EmptyState";
import { LoadingState } from "../../src/components/LoadingState";
import { colors } from "../../src/theme/colors";
import { EventCategory } from "../../src/types/event";

const CATEGORIES: EventCategory[] = ["Music","Nightlife","Culture","Theatre","Student","Food & Drink","Markets","Workshops","Comedy","Exhibitions"];

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
      <View style={styles.header}><Text style={styles.eyebrow}>DISCOVER</Text><Text style={styles.heading}>Explore</Text></View>
      <View style={styles.searchBar}>
        <Ionicons name="search" size={18} color={colors.textMuted} />
        <TextInput style={styles.input} placeholder="Search events, places, vibes..." placeholderTextColor={colors.textMuted} value={query} onChangeText={setQuery} autoCorrect={false} />
        {query.length > 0 && <Pressable onPress={() => setQuery("")}><Ionicons name="close-circle" size={18} color={colors.textMuted} /></Pressable>}
      </View>
      {!isSearching && (
        <FlatList horizontal data={CATEGORIES} keyExtractor={(c) => c} showsHorizontalScrollIndicator={false} style={styles.chips} contentContainerStyle={styles.chipContent}
          renderItem={({ item }) => {
            const active = category === item;
            return <Pressable style={[styles.chip, active && styles.chipActive]} onPress={() => setCategory(active ? null : item)}>
              <Text style={[styles.chipText, active && styles.chipTextActive]}>{item}</Text>
            </Pressable>;
          }}
        />
      )}
      {isLoading ? <LoadingState /> : isError ? <EmptyState title="Something went wrong" subtitle="Couldn't reach the API." /> : (
        <FlatList data={items ?? []} keyExtractor={(item) => item.id} contentContainerStyle={styles.results} showsVerticalScrollIndicator={false}
          renderItem={({ item }) => <EventCard event={item} />}
          ListHeaderComponent={<Text style={styles.resultLabel}>{items?.length ?? 0} events</Text>}
          ListEmptyComponent={<EmptyState title={isSearching ? "No matches" : "No events here yet"} subtitle={isSearching ? "Nothing found for: " + query : undefined} />}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: { paddingHorizontal: 18, paddingTop: 12, paddingBottom: 14 },
  eyebrow: { color: colors.accent, fontSize: 10, fontWeight: "900", letterSpacing: 1.4 },
  heading: { color: colors.text, fontSize: 32, fontWeight: "900", letterSpacing: -0.8, marginTop: 2 },
  searchBar: { marginHorizontal: 18, flexDirection: "row", alignItems: "center", gap: 9, paddingHorizontal: 14, height: 50, borderRadius: 16, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border },
  input: { flex: 1, color: colors.text, fontSize: 14 },
  chips: { flexGrow: 0, marginTop: 12, marginBottom: 2 },
  chipContent: { gap: 8, paddingHorizontal: 18 },
  chip: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 99, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { color: colors.textMuted, fontSize: 11, fontWeight: "800" },
  chipTextActive: { color: colors.white },
  results: { padding: 18, paddingBottom: 110 },
  resultLabel: { color: colors.textMuted, fontSize: 11, fontWeight: "700", marginBottom: 10 },
});