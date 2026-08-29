/**
 * Home screen (spec section 40): "Tonight" / "This weekend" / "Coming up"
 * sections built by grouping the same /events response client-side — one
 * network call, three shelves. Pull-to-refresh re-fetches from the API.
 */
import { useMemo } from "react";
import { FlatList, RefreshControl, SectionList, StyleSheet, Text, View } from "react-native";
import { useEvents } from "../../src/hooks/useEvents";
import { EventCard } from "../../src/components/EventCard";
import { EmptyState } from "../../src/components/EmptyState";
import { LoadingState } from "../../src/components/LoadingState";
import { colors } from "../../src/theme/colors";
import { EventOut } from "../../src/types/event";

function isSameDay(a: Date, b: Date) {
  return a.toDateString() === b.toDateString();
}

function isThisWeekend(d: Date, now: Date) {
  const day = d.getDay(); // 0 = Sun, 6 = Sat
  const diffDays = (d.getTime() - now.getTime()) / 86_400_000;
  return diffDays >= 0 && diffDays <= 7 && (day === 0 || day === 6);
}

function groupEvents(events: EventOut[]) {
  const now = new Date();
  const tonight: EventOut[] = [];
  const weekend: EventOut[] = [];
  const upcoming: EventOut[] = [];

  for (const e of events) {
    const start = new Date(e.start_time);
    if (isSameDay(start, now)) {
      tonight.push(e);
    } else if (isThisWeekend(start, now)) {
      weekend.push(e);
    } else {
      upcoming.push(e);
    }
  }

  return [
    { title: "Tonight", data: tonight },
    { title: "This weekend", data: weekend },
    { title: "Coming up", data: upcoming },
  ].filter((section) => section.data.length > 0);
}

export default function HomeScreen() {
  const { data, isLoading, isError, refetch, isRefetching } = useEvents({ limit: 50 });

  const sections = useMemo(() => groupEvents(data?.items ?? []), [data]);

  if (isLoading) return <LoadingState />;

  if (isError) {
    return (
      <EmptyState
        title="Couldn't load events"
        subtitle="Check that the API is running and EXPO_PUBLIC_API_URL is set correctly."
      />
    );
  }

  return (
    <SectionList
      style={styles.container}
      contentContainerStyle={styles.content}
      sections={sections}
      keyExtractor={(item) => item.id}
      renderItem={({ item }) => <EventCard event={item} />}
      renderSectionHeader={({ section }) => (
        <Text style={styles.sectionHeader}>{section.title}</Text>
      )}
      refreshControl={
        <RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor={colors.primary} />
      }
      ListHeaderComponent={<Text style={styles.heading}>What's happening in Bratislava</Text>}
      ListEmptyComponent={
        <EmptyState
          title="No upcoming events yet"
          subtitle="Once the crawler has run, fresh Bratislava events will show up here."
        />
      }
    />
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: 16, paddingBottom: 32 },
  heading: { color: colors.text, fontSize: 22, fontWeight: "800", marginBottom: 16 },
  sectionHeader: {
    color: colors.text,
    fontSize: 15,
    fontWeight: "700",
    marginTop: 12,
    marginBottom: 8,
  },
});