/**
 * Saved events (spec section 38). Requires auth — logged-out users see a
 * prompt pointing at the Profile tab instead of an empty list.
 */
import { router } from "expo-router";
import { FlatList, Pressable, StyleSheet, Text } from "react-native";
import { useAuthStore } from "../../src/store/authStore";
import { useSavedEvents } from "../../src/hooks/useEvents";
import { EventCard } from "../../src/components/EventCard";
import { EmptyState } from "../../src/components/EmptyState";
import { LoadingState } from "../../src/components/LoadingState";
import { colors } from "../../src/theme/colors";

export default function SavedScreen() {
  const token = useAuthStore((s) => s.token);
  const { data, isLoading, isError } = useSavedEvents();

  if (!token) {
    return (
      <EmptyState
        title="Log in to save events"
        subtitle="Create an account or log in from the Profile tab to start saving events."
      />
    );
  }

  if (isLoading) return <LoadingState />;
  if (isError) return <EmptyState title="Couldn't load saved events" />;

  return (
    <FlatList
      style={styles.container}
      contentContainerStyle={styles.content}
      data={data ?? []}
      keyExtractor={(item) => item.id}
      renderItem={({ item }) => <EventCard event={item} />}
      ListEmptyComponent={
        <EmptyState title="No saved events yet" subtitle="Tap the save icon on any event to add it here." />
      }
    />
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: 16, paddingBottom: 32 },
});