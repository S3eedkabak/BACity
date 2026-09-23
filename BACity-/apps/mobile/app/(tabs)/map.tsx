import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View } from "react-native";
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
        pitchEnabled={false}
        rotateEnabled={false}
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

      <View pointerEvents="box-none" style={StyleSheet.absoluteFillObject}>
        <View style={styles.header}>
          <View>
            <Text style={styles.eyebrow}>OUT AND ABOUT</Text>
            <Text style={styles.heading}>Map</Text>
          </View>
          <Pressable style={styles.locateButton}>
            <Ionicons name="navigate" size={18} color={colors.primary} />
            <Text style={styles.locateText}>Near me</Text>
          </Pressable>
        </View>

        <View style={styles.searchBar}>
          <Ionicons name="search" size={18} color={colors.primary} />
          <Text style={styles.searchText}>Search this area</Text>
        </View>

        <View style={styles.counter}>
          <View style={styles.counterDot} />
          <Text style={styles.counterText}>{pins.length} events with a location</Text>
        </View>

        {!pins.length && (
          <View style={styles.emptyCard}>
            <View style={styles.emptyIcon}>
              <Ionicons name="map-outline" size={22} color={colors.primary} />
            </View>
            <View style={styles.emptyCopy}>
              <Text style={styles.emptyTitle}>The map is waiting</Text>
              <Text style={styles.emptyText}>
                Events need coordinates before they can appear here.
              </Text>
            </View>
          </View>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.mapWater },
  header: {
    marginTop: 14,
    marginHorizontal: 18,
    padding: 15,
    borderRadius: 22,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    shadowColor: colors.shadow,
    shadowOpacity: 0.1,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 5 },
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
    fontSize: 30,
    letterSpacing: -0.8,
    marginTop: 1,
  },
  locateButton: {
    height: 40,
    borderRadius: 15,
    paddingHorizontal: 11,
    backgroundColor: colors.primarySoft,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  locateText: { color: colors.text, fontFamily: fonts.semibold, fontSize: 10 },
  searchBar: {
    marginTop: 10,
    marginHorizontal: 18,
    height: 50,
    borderRadius: 18,
    paddingHorizontal: 15,
    backgroundColor: colors.surface,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    borderWidth: 1,
    borderColor: colors.border,
  },
  searchText: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 12 },
  counter: {
    alignSelf: "flex-start",
    marginTop: 10,
    marginLeft: 18,
    paddingHorizontal: 12,
    height: 30,
    borderRadius: 15,
    backgroundColor: colors.text,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  counterDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: colors.primary },
  counterText: { color: colors.background, fontFamily: fonts.medium, fontSize: 9 },
  emptyCard: {
    position: "absolute",
    left: 18,
    right: 18,
    bottom: 96,
    minHeight: 100,
    borderRadius: 24,
    padding: 16,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    flexDirection: "row",
    alignItems: "center",
    shadowColor: colors.shadow,
    shadowOpacity: 0.12,
    shadowRadius: 16,
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
  emptyCopy: { flex: 1, marginLeft: 12 },
  emptyTitle: { color: colors.text, fontFamily: fonts.black, fontSize: 16 },
  emptyText: {
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 10,
    lineHeight: 15,
    marginTop: 4,
  },
});
