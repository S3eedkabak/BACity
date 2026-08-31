import { Ionicons } from "@expo/vector-icons";
import { StyleSheet, Text, View } from "react-native";
import MapView, { Marker } from "react-native-maps";
import { router } from "expo-router";
import { useEvents } from "../../src/hooks/useEvents";
import { LoadingState } from "../../src/components/LoadingState";
import { colors } from "../../src/theme/colors";

const BRATISLAVA_REGION = {
  latitude: 48.1486,
  longitude: 17.1077,
  latitudeDelta: 0.08,
  longitudeDelta: 0.08,
};

export default function MapScreen() {
  const { data, isLoading } = useEvents({ limit: 100 });
  const pins = (data?.items ?? []).filter(
    (event) => event.latitude != null && event.longitude != null
  );

  if (isLoading) return <LoadingState />;

  return (
    <View style={styles.container}>
      <MapView
        style={StyleSheet.absoluteFillObject}
        initialRegion={BRATISLAVA_REGION}
        showsUserLocation={false}
      >
        {pins.map((event) => (
          <Marker
            key={event.id}
            coordinate={{
              latitude: event.latitude as number,
              longitude: event.longitude as number,
            }}
            title={event.title}
            description={event.venue?.name ?? event.address ?? undefined}
            onCalloutPress={() => router.push(`/event/${event.id}`)}
          />
        ))}
      </MapView>

      <View style={styles.header}>
        <Text style={styles.eyebrow}>AROUND YOU</Text>
        <Text style={styles.heading}>Map</Text>
      </View>

      <View style={styles.counter}>
        <Ionicons name="location" size={15} color={colors.accent} />
        <Text style={styles.counterText}>{pins.length} mapped events</Text>
      </View>

      {!pins.length && (
        <View style={styles.empty}>
          <Ionicons name="map-outline" size={26} color={colors.textMuted} />
          <Text style={styles.emptyTitle}>No mapped events yet</Text>
          <Text style={styles.emptyText}>
            Events need coordinates before they can appear here.
          </Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: {
    position: "absolute",
    top: 14,
    left: 18,
    right: 18,
    padding: 15,
    borderRadius: 20,
    backgroundColor: "rgba(10,10,15,0.88)",
    borderWidth: 1,
    borderColor: colors.border,
  },
  eyebrow: { color: colors.accent, fontSize: 9, fontWeight: "900", letterSpacing: 1.4 },
  heading: { color: colors.text, fontSize: 27, fontWeight: "900", marginTop: 2 },
  counter: {
    position: "absolute",
    top: 103,
    alignSelf: "center",
    flexDirection: "row",
    gap: 6,
    alignItems: "center",
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 99,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  counterText: { color: colors.text, fontSize: 11, fontWeight: "800" },
  empty: {
    position: "absolute",
    bottom: 35,
    left: 25,
    right: 25,
    padding: 20,
    borderRadius: 20,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
  },
  emptyTitle: { color: colors.text, fontWeight: "900", fontSize: 15, marginTop: 8 },
  emptyText: { color: colors.textMuted, textAlign: "center", fontSize: 12, marginTop: 4 },
});
