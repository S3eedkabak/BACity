import { Ionicons } from "@expo/vector-icons";
import {
  Camera,
  MapView,
  PointAnnotation,
} from "@maplibre/maplibre-react-native";
import { router } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useEvents } from "../../src/hooks/useEvents";
import { LoadingState } from "../../src/components/LoadingState";
import { colors } from "../../src/theme/colors";
import { fonts } from "../../src/theme/fonts";

const BRATISLAVA = {
  longitude: 17.1077,
  latitude: 48.1486,
};

const OPEN_FREE_MAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";

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
        styleURL={OPEN_FREE_MAP_STYLE}
        compassEnabled={false}
        rotateEnabled={false}
        pitchEnabled={false}
        attributionEnabled
        logoEnabled
      >
        <Camera
          defaultSettings={{
            centerCoordinate: [BRATISLAVA.longitude, BRATISLAVA.latitude],
            zoomLevel: 12,
            pitch: 0,
            heading: 0,
          }}
        />

        {pins.map((event) => (
          <PointAnnotation
            key={event.id}
            id={event.id}
            coordinate={[
              event.longitude as number,
              event.latitude as number,
            ]}
            title={event.title}
            snippet={event.venue?.name ?? event.address ?? "Bratislava"}
            onSelected={() => router.push("/event/" + event.id)}
          >
            <View style={styles.annotation}>
              <View style={styles.annotationInner}>
                <Ionicons name="heart" size={11} color={colors.white} />
              </View>
            </View>
          </PointAnnotation>
        ))}
      </MapView>

      <View pointerEvents="box-none" style={StyleSheet.absoluteFillObject}>
        <View style={styles.header}>
          <Text style={styles.heading}>Map</Text>
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
          <Text style={styles.counterText}>
            {pins.length} events with a location
          </Text>
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
  container: {
    flex: 1,
    backgroundColor: colors.mapWater,
  },
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
  heading: {
    color: colors.text,
    fontFamily: fonts.black,
    fontSize: 30,
    letterSpacing: -0.8,
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
  locateText: {
    color: colors.text,
    fontFamily: fonts.semibold,
    fontSize: 10,
  },
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
  searchText: {
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 12,
  },
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
  counterDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.primary,
  },
  counterText: {
    color: colors.background,
    fontFamily: fonts.medium,
    fontSize: 9,
  },
  annotation: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
  },
  annotationInner: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: colors.primary,
    borderWidth: 3,
    borderColor: colors.white,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: colors.shadow,
    shadowOpacity: 0.25,
    shadowRadius: 7,
    shadowOffset: { width: 0, height: 3 },
  },
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
  emptyCopy: {
    flex: 1,
    marginLeft: 12,
  },
  emptyTitle: {
    color: colors.text,
    fontFamily: fonts.black,
    fontSize: 16,
  },
  emptyText: {
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 10,
    lineHeight: 15,
    marginTop: 4,
  },
});
