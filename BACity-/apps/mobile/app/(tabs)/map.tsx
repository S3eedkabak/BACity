import { Ionicons } from "@expo/vector-icons";
import { StyleSheet, Text, View } from "react-native";
import MapView, { Marker } from "react-native-maps";
import { router } from "expo-router";
import { useEvents } from "../../src/hooks/useEvents";
import { LoadingState } from "../../src/components/LoadingState";
import { colors } from "../../src/theme/colors";
import { fonts } from "../../src/theme/fonts";

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
        showsCompass={false}
        toolbarEnabled={false}
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
            pinColor={colors.primary}
            onCalloutPress={() => router.push("/event/" + event.id)}
          />
        ))}
      </MapView>

      <View style={styles.header}>
        <View>
          <Text style={styles.eyebrow}>OUT AND ABOUT</Text>
          <Text style={styles.heading}>Map</Text>
        </View>
        <View style={styles.mapIcon}>
          <Ionicons name="navigate" size={17} color={colors.primary} />
        </View>
      </View>

      <View style={styles.counter}>
        <View style={styles.counterDot} />
        <Text style={styles.counterText}>{pins.length} events with a location</Text>
      </View>

      {!pins.length && (
        <View style={styles.empty}>
          <View style={styles.emptyIcon}>
            <Ionicons name="map-outline" size={23} color={colors.primary} />
          </View>
          <Text style={styles.emptyTitle}>The map is waiting</Text>
          <Text style={styles.emptyText}>
            Events need coordinates before they can appear here.
          </Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.mapWater },
  header: {
    position: "absolute",
    top: 14,
    left: 18,
    right: 18,
    padding: 15,
    borderRadius: 22,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    shadowColor: colors.shadow,
    shadowOpacity: 0.13,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 7 },
  },
  eyebrow: {
    color: colors.primaryDark,
    fontFamily: fonts.semibold,
    fontSize: 9,
    letterSpacing: 1.3,
  },
  heading: {
    color: colors.text,
    fontFamily: fonts.black,
    fontSize: 28,
    marginTop: 1,
  },
  mapIcon: {
    width: 40,
    height: 40,
    borderRadius: 14,
    backgroundColor: colors.primarySoft,
    alignItems: "center",
    justifyContent: "center",
  },
  counter: {
    position: "absolute",
    top: 101,
    alignSelf: "center",
    flexDirection: "row",
    gap: 6,
    alignItems: "center",
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 99,
    backgroundColor: colors.text,
    shadowColor: colors.shadow,
    shadowOpacity: 0.16,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
  },
  counterDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    backgroundColor: colors.primary,
  },
  counterText: { color: colors.white, fontFamily: fonts.semibold, fontSize: 10 },
  empty: {
    position: "absolute",
    bottom: 34,
    left: 25,
    right: 25,
    padding: 20,
    borderRadius: 22,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    shadowColor: colors.shadow,
    shadowOpacity: 0.13,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 7 },
  },
  emptyIcon: {
    width: 48,
    height: 48,
    borderRadius: 17,
    backgroundColor: colors.primarySoft,
    alignItems: "center",
    justifyContent: "center",
  },
  emptyTitle: { color: colors.text, fontFamily: fonts.black, fontSize: 16, marginTop: 10 },
  emptyText: {
    color: colors.textMuted,
    fontFamily: fonts.regular,
    textAlign: "center",
    fontSize: 11,
    lineHeight: 17,
    marginTop: 4,
  },
});
