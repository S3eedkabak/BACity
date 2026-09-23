import { useState } from "react";
import {
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useEvents, useSearchEvents } from "../../src/hooks/useEvents";
import { EventCard } from "../../src/components/EventCard";
import { EmptyState } from "../../src/components/EmptyState";
import { LoadingState } from "../../src/components/LoadingState";
import { colors } from "../../src/theme/colors";
import { fonts } from "../../src/theme/fonts";
import { EventCategory } from "../../src/types/event";

const CATEGORIES: EventCategory[] = [
  "Music",
  "Nightlife",
  "Culture",
  "Theatre",
  "Student",
  "Food & Drink",
  "Markets",
  "Workshops",
  "Comedy",
  "Exhibitions",
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
      <FlatList
        data={items ?? []}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
        ListHeaderComponent={
          <>
            <View style={styles.header}>
              <View>
                <Text style={styles.eyebrow}>THE CITY IS YOURS</Text>
                <Text style={styles.heading}>Explore</Text>
              </View>
              <View style={styles.headerButton}>
                <Ionicons name="sparkles-outline" size={20} color={colors.primary} />
              </View>
            </View>

            <View style={styles.searchBar}>
              <View style={styles.searchIcon}>
                <Ionicons name="search" size={19} color={colors.primary} />
              </View>
              <TextInput
                style={styles.input}
                placeholder="Search events, places, vibes..."
                placeholderTextColor={colors.textMuted}
                value={query}
                onChangeText={setQuery}
                autoCorrect={false}
              />
              {query.length > 0 && (
                <Pressable onPress={() => setQuery("")} hitSlop={10}>
                  <Ionicons name="close-circle" size={19} color={colors.textMuted} />
                </Pressable>
              )}
            </View>

            {!isSearching && (
              <View style={styles.filterSection}>
                <View style={styles.filterHeader}>
                  <Text style={styles.filterTitle}>Browse by vibe</Text>
                  {category && (
                    <Pressable onPress={() => setCategory(null)}>
                      <Text style={styles.clear}>Clear</Text>
                    </Pressable>
                  )}
                </View>
                <FlatList
                  horizontal
                  data={CATEGORIES}
                  keyExtractor={(c) => c}
                  showsHorizontalScrollIndicator={false}
                  contentContainerStyle={styles.chips}
                  renderItem={({ item }) => {
                    const active = category === item;
                    return (
                      <Pressable
                        style={[styles.chip, active && styles.chipActive]}
                        onPress={() => setCategory(active ? null : item)}
                      >
                        <Text style={[styles.chipText, active && styles.chipTextActive]}>
                          {item}
                        </Text>
                      </Pressable>
                    );
                  }}
                />
              </View>
            )}

            <View style={styles.resultHeader}>
              <View>
                <Text style={styles.resultTitle}>
                  {isSearching ? "Search results" : "What's on"}
                </Text>
                <Text style={styles.resultSubtitle}>
                  {isSearching ? "Matching your search" : "Fresh plans around the city"}
                </Text>
              </View>
              <View style={styles.countPill}>
                <Text style={styles.resultCount}>{items?.length ?? 0}</Text>
              </View>
            </View>

            {isLoading && <LoadingState />}
            {isError && (
              <EmptyState
                title="Couldn't reach the city"
                subtitle="Check that the API is running."
              />
            )}
          </>
        }
        renderItem={({ item }) => <EventCard event={item} />}
        ListEmptyComponent={
          !isLoading && !isError ? (
            <EmptyState
              title={isSearching ? "No matches yet" : "No events here yet"}
              subtitle={
                isSearching
                  ? "Try a different word or category."
                  : "Fresh events will appear after the next crawl."
              }
            />
          ) : null
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { paddingHorizontal: 18, paddingTop: 12, paddingBottom: 108 },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 18,
  },
  eyebrow: {
    color: colors.primaryDark,
    fontFamily: fonts.semibold,
    fontSize: 9,
    letterSpacing: 1.4,
  },
  heading: {
    color: colors.text,
    fontFamily: fonts.black,
    fontSize: 36,
    letterSpacing: -1.2,
    marginTop: 2,
  },
  headerButton: {
    width: 44,
    height: 44,
    borderRadius: 16,
    backgroundColor: colors.primarySoft,
    alignItems: "center",
    justifyContent: "center",
  },
  searchBar: {
    height: 58,
    borderRadius: 20,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 8,
    shadowColor: colors.shadow,
    shadowOpacity: 0.07,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 5 },
  },
  searchIcon: {
    width: 42,
    height: 42,
    borderRadius: 14,
    backgroundColor: colors.primarySoft,
    alignItems: "center",
    justifyContent: "center",
  },
  input: {
    flex: 1,
    color: colors.text,
    fontFamily: fonts.regular,
    fontSize: 13,
    marginHorizontal: 10,
  },
  filterSection: { marginTop: 22 },
  filterHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 10,
  },
  filterTitle: { color: colors.text, fontFamily: fonts.semibold, fontSize: 13 },
  clear: { color: colors.primaryDark, fontFamily: fonts.semibold, fontSize: 11 },
  chips: { gap: 8, paddingRight: 10 },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 9,
    borderRadius: 99,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { color: colors.textMuted, fontFamily: fonts.semibold, fontSize: 11 },
  chipTextActive: { color: colors.white },
  resultHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: 25,
    marginBottom: 12,
  },
  resultTitle: { color: colors.text, fontFamily: fonts.black, fontSize: 20 },
  resultSubtitle: {
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 10,
    marginTop: 2,
  },
  countPill: {
    minWidth: 32,
    height: 32,
    paddingHorizontal: 9,
    borderRadius: 16,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  resultCount: { color: colors.white, fontFamily: fonts.black, fontSize: 11 },
});
