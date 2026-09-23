import { Ionicons } from "@expo/vector-icons";
import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { useAuthStore } from "../../src/store/authStore";
import { useSavedEvents } from "../../src/hooks/useEvents";
import { EventCard } from "../../src/components/EventCard";
import { EmptyState } from "../../src/components/EmptyState";
import { LoadingState } from "../../src/components/LoadingState";
import { colors } from "../../src/theme/colors";
import { fonts } from "../../src/theme/fonts";
import { router } from "expo-router";

export default function SavedScreen() {
  const token = useAuthStore((s) => s.token);
  const { data, isLoading, isError } = useSavedEvents();

  if (!token) {
    return (
      <View style={styles.guest}>
        <View style={styles.guestBlob}>
          <Ionicons name="heart" size={28} color={colors.white} />
        </View>
        <Text style={styles.eyebrow}>YOUR PLANS</Text>
        <Text style={styles.title}>Keep the good stuff.</Text>
        <Text style={styles.subtitle}>
          Save events you love and build a little list of things worth doing.
        </Text>
        <Pressable style={styles.loginButton} onPress={() => router.push("/(tabs)/profile")}>
          <Text style={styles.loginText}>Log in to save events</Text>
          <Ionicons name="arrow-forward" size={17} color={colors.white} />
        </Pressable>
      </View>
    );
  }

  if (isLoading) return <LoadingState />;
  if (isError) return <EmptyState title="Couldn't load saved events" subtitle="Try again in a moment." />;

  return (
    <FlatList
      style={styles.container}
      contentContainerStyle={styles.content}
      data={data ?? []}
      keyExtractor={(item) => item.id}
      showsVerticalScrollIndicator={false}
      ListHeaderComponent={
        <View style={styles.header}>
          <Text style={styles.eyebrow}>YOUR PICKS</Text>
          <View style={styles.headingRow}>
            <Text style={styles.heading}>Saved</Text>
            <View style={styles.countPill}>
              <Text style={styles.count}>{data?.length ?? 0}</Text>
            </View>
          </View>
          <Text style={styles.headerText}>The events you said yes to.</Text>
        </View>
      }
      renderItem={({ item }) => <EventCard event={item} />}
      ListEmptyComponent={
        <EmptyState title="Nothing saved yet" subtitle="Your best finds will collect here." />
      }
    />
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: 18, paddingTop: 10, paddingBottom: 115 },
  header: { paddingBottom: 18 },
  eyebrow: {
    color: colors.primaryDark,
    fontFamily: fonts.semibold,
    fontSize: 9,
    letterSpacing: 1.4,
  },
  headingRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  heading: {
    color: colors.text,
    fontFamily: fonts.black,
    fontSize: 36,
    letterSpacing: -1.1,
    marginTop: 2,
  },
  countPill: {
    minWidth: 27,
    height: 27,
    paddingHorizontal: 8,
    borderRadius: 14,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 6,
  },
  count: { color: colors.white, fontFamily: fonts.black, fontSize: 11 },
  headerText: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 12, marginTop: 2 },
  guest: {
    flex: 1,
    backgroundColor: colors.background,
    alignItems: "center",
    justifyContent: "center",
    padding: 32,
  },
  guestBlob: {
    width: 74,
    height: 74,
    borderRadius: 28,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 20,
    transform: [{ rotate: "-6deg" }],
  },
  title: {
    color: colors.text,
    fontFamily: fonts.black,
    fontSize: 29,
    textAlign: "center",
    letterSpacing: -0.8,
    marginTop: 2,
  },
  subtitle: {
    color: colors.textMuted,
    fontFamily: fonts.regular,
    textAlign: "center",
    lineHeight: 21,
    marginTop: 9,
    fontSize: 13,
    maxWidth: 300,
  },
  loginButton: {
    height: 52,
    borderRadius: 17,
    backgroundColor: colors.text,
    paddingHorizontal: 18,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginTop: 24,
  },
  loginText: { color: colors.white, fontFamily: fonts.semibold, fontSize: 12 },
});
