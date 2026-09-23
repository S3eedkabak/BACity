import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";
import { useEvents } from "../../src/hooks/useEvents";
import { LoadingState } from "../../src/components/LoadingState";
import { colors } from "../../src/theme/colors";
import { fonts } from "../../src/theme/fonts";

const BRATISLAVA = {
  latitude: 48.1486,
  longitude: 17.1077,
};

const MAP_BOUNDS = {
  minLat: 48.105,
  maxLat: 48.205,
  minLng: 17.035,
  maxLng: 17.185,
};

function project(latitude: number, longitude: number) {
  const x =
    ((longitude - MAP_BOUNDS.minLng) /
      (MAP_BOUNDS.maxLng - MAP_BOUNDS.minLng)) *
    100;
  const y =
    (1 -
      (latitude - MAP_BOUNDS.minLat) /
        (MAP_BOUNDS.maxLat - MAP_BOUNDS.minLat)) *
    100;

  return {
    left: `${Math.max(4, Math.min(96, x))}%` as `${number}%`,
    top: `${Math.max(5, Math.min(95, y))}%` as `${number}%`,
  };
}

export default function MapScreen() {
  const { data, isLoading } = useEvents({ limit: 100 });
  const pins = (data?.items ?? []).filter(
    (event) => event.latitude != null && event.longitude != null
  );

  if (isLoading) return <LoadingState />;

  return (
    <View style={styles.container}>
      <View style={styles.map}>
        <View style={[styles.water, styles.waterTop]} />
        <View style={[styles.water, styles.waterBottom]} />

        <View style={[styles.road, styles.roadOne]} />
        <View style={[styles.road, styles.roadTwo]} />
        <View style={[styles.road, styles.roadThree]} />
        <View style={[styles.road, styles.roadFour]} />
        <View style={[styles.road, styles.roadFive]} />

        <View style={[styles.district, styles.districtOne]} />
        <View style={[styles.district, styles.districtTwo]} />
        <View style={[styles.district, styles.districtThree]} />

        <Text style={[styles.mapLabel, styles.oldTownLabel]}>STARÉ MESTO</Text>
        <Text style={[styles.mapLabel, styles.petrzalkaLabel]}>PETRŽALKA</Text>
        <Text style={[styles.mapLabel, styles.ruzinovLabel]}>RUŽINOV</Text>

        <View
          style={[
            styles.cityDot,
            {
              left: `${project(BRATISLAVA.latitude, BRATISLAVA.longitude).left}`,
              top: `${project(BRATISLAVA.latitude, BRATISLAVA.longitude).top}`,
            },
          ]}
        />

        {pins.map((event) => {
          const position = project(
            event.latitude as number,
            event.longitude as number
          );

          return (
            <Pressable
              key={event.id}
              style={[
                styles.marker,
                { left: position.left, top: position.top },
              ]}
              onPress={() => router.push("/event/" + event.id)}
              accessibilityRole="button"
              accessibilityLabel={`Open ${event.title}`}
            >
              <View style={styles.markerInner}>
                <Ionicons name="heart" size={11} color={colors.white} />
              </View>
            </Pressable>
          );
        })}
      </View>

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
        <Text style={styles.counterText}>
          {pins.length} events with a location
        </Text>
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
  map: {
    ...StyleSheet.absoluteFillObject,
    overflow: "hidden",
    backgroundColor: "#F2F4EC",
  },
  water: {
    position: "absolute",
    backgroundColor: colors.mapWater,
    borderRadius: 999,
  },
  waterTop: {
    width: "74%",
    height: "33%",
    right: "-18%",
    top: "-13%",
    transform: [{ rotate: "-12deg" }],
  },
  waterBottom: {
    width: "64%",
    height: "24%",
    left: "-20%",
    bottom: "-8%",
    transform: [{ rotate: "8deg" }],
  },
  district: {
    position: "absolute",
    borderWidth: 1,
    borderColor: "#E1E5DA",
    backgroundColor: "#F8F8F2",
    borderRadius: 30,
  },
  districtOne: {
    width: "42%",
    height: "40%",
    left: "30%",
    top: "30%",
    transform: [{ rotate: "-9deg" }],
  },
  districtTwo: {
    width: "32%",
    height: "29%",
    left: "2%",
    top: "38%",
    transform: [{ rotate: "7deg" }],
  },
  districtThree: {
    width: "36%",
    height: "31%",
    right: "1%",
    top: "25%",
    transform: [{ rotate: "11deg" }],
  },
  road: {
    position: "absolute",
    backgroundColor: "#E3E2D9",
    borderRadius: 99,
    opacity: 0.9,
  },
  roadOne: {
    width: "115%",
    height: 9,
    left: "-7%",
    top: "46%",
    transform: [{ rotate: "-18deg" }],
  },
  roadTwo: {
    width: "105%",
    height: 7,
    left: "-4%",
    top: "59%",
    transform: [{ rotate: "12deg" }],
  },
  roadThree: {
    width: 7,
    height: "110%",
    left: "48%",
    top: "-5%",
    transform: [{ rotate: "23deg" }],
  },
  roadFour: {
    width: 6,
    height: "105%",
    left: "69%",
    top: "-4%",
    transform: [{ rotate: "-18deg" }],
  },
  roadFive: {
    width: "80%",
    height: 5,
    left: "9%",
    top: "30%",
    transform: [{ rotate: "32deg" }],
  },
  mapLabel: {
    position: "absolute",
    color: "#AAA99E",
    fontFamily: fonts.semibold,
    fontSize: 8,
    letterSpacing: 1,
  },
  oldTownLabel: { left: "40%", top: "39%" },
  petrzalkaLabel: { left: "18%", bottom: "17%" },
  ruzinovLabel: { right: "10%", top: "43%" },
  cityDot: {
    position: "absolute",
    width: 12,
    height: 12,
    marginLeft: -6,
    marginTop: -6,
    borderRadius: 6,
    backgroundColor: colors.text,
    borderWidth: 3,
    borderColor: colors.surface,
  },
  marker: {
    position: "absolute",
    width: 34,
    height: 34,
    marginLeft: -17,
    marginTop: -17,
    alignItems: "center",
    justifyContent: "center",
    cursor: "pointer",
  } as any,
  markerInner: {
    width: 27,
    height: 27,
    borderRadius: 14,
    backgroundColor: colors.primary,
    borderWidth: 3,
    borderColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: colors.shadow,
    shadowOpacity: 0.25,
    shadowRadius: 7,
    shadowOffset: { width: 0, height: 3 },
  },
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
  counterText: {
    color: colors.white,
    fontFamily: fonts.semibold,
    fontSize: 10,
  },
  empty: {
    position: "absolute",
    bottom: 96,
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
  emptyTitle: {
    color: colors.text,
    fontFamily: fonts.black,
    fontSize: 16,
    marginTop: 10,
  },
  emptyText: {
    color: colors.textMuted,
    fontFamily: fonts.regular,
    textAlign: "center",
    fontSize: 11,
    lineHeight: 17,
    marginTop: 4,
  },
});
