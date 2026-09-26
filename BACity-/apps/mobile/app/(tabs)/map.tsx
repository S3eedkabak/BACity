import { Ionicons } from "@expo/vector-icons";
import type {
  CameraRef,
  MapViewRef,
} from "@maplibre/maplibre-react-native";
import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { useMemo, useRef, useState } from "react";
import { Platform, Pressable, StyleSheet, Text, View } from "react-native";
import { useEvents } from "../../src/hooks/useEvents";
import { LoadingState } from "../../src/components/LoadingState";
import { colors } from "../../src/theme/colors";
import { fonts } from "../../src/theme/fonts";
import { nearbyUtilities, utilitiesInViewport, type UtilityBounds } from "../../src/api/utilities";

// Expo Router evaluates route modules while building its web route context. Avoid
// initializing the native MapLibre bridge during that discovery pass.
const nativeMapLibre =
  Platform.OS === "web"
    ? null
    : (require("@maplibre/maplibre-react-native") as typeof import("@maplibre/maplibre-react-native"));

const {
  Camera,
  CircleLayer,
  MapView,
  PointAnnotation,
  ShapeSource,
  SymbolLayer,
  UserLocation,
  UserTrackingMode,
} = nativeMapLibre ?? ({} as typeof import("@maplibre/maplibre-react-native"));

const BRATISLAVA = {
  longitude: 17.1077,
  latitude: 48.1486,
};

const OPEN_FREE_MAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";
const NEARBY_RADIUS_KM = 3;
const INITIAL_BOUNDS: UtilityBounds = {
  min_lat: 48.105,
  max_lat: 48.205,
  min_lng: 17.035,
  max_lng: 17.185,
};

type Coordinates = {
  latitude: number;
  longitude: number;
};

function distanceKm(a: Coordinates, b: Coordinates) {
  const earthRadiusKm = 6371;
  const lat1 = (a.latitude * Math.PI) / 180;
  const lat2 = (b.latitude * Math.PI) / 180;
  const deltaLat = ((b.latitude - a.latitude) * Math.PI) / 180;
  const deltaLng = ((b.longitude - a.longitude) * Math.PI) / 180;

  const haversine =
    Math.sin(deltaLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(deltaLng / 2) ** 2;

  return 2 * earthRadiusKm * Math.asin(Math.sqrt(haversine));
}

export default function MapScreen() {
  const { data, isLoading } = useEvents({ limit: 100 });
  const cameraRef = useRef<CameraRef>(null);
  const mapRef = useRef<MapViewRef>(null);
  const [nearMeActive, setNearMeActive] = useState(false);
  const [showUtilities, setShowUtilities] = useState(false);
  const [utilityBounds, setUtilityBounds] = useState(INITIAL_BOUNDS);
  const [currentLocation, setCurrentLocation] = useState<Coordinates | null>(
    null
  );

  const pins = useMemo(
    () =>
      (data?.items ?? []).filter(
        (event) => event.latitude != null && event.longitude != null
      ),
    [data?.items]
  );

  const nearbyPins = useMemo(() => {
    if (!currentLocation) return [];
    return pins.filter(
      (event) =>
        distanceKm(currentLocation, {
          latitude: event.latitude as number,
          longitude: event.longitude as number,
        }) <= NEARBY_RADIUS_KM
    );
  }, [currentLocation, pins]);

  const utilityViewport = useQuery({
    queryKey: ["utilities-viewport", utilityBounds],
    queryFn: () => utilitiesInViewport(utilityBounds),
    enabled: showUtilities && !nearMeActive,
    staleTime: 60_000,
  });
  const utilityNearby = useQuery({
    queryKey: ["utilities-nearby", currentLocation],
    queryFn: () => nearbyUtilities(currentLocation!.latitude, currentLocation!.longitude, NEARBY_RADIUS_KM),
    enabled: showUtilities && nearMeActive && currentLocation != null,
    staleTime: 60_000,
  });
  const utilities = (nearMeActive ? utilityNearby.data : utilityViewport.data) ?? [];
  const utilityShape = useMemo(() => ({
    type: "FeatureCollection" as const,
    features: utilities.map((utility) => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [utility.longitude, utility.latitude] },
      properties: { id: utility.id, name: utility.name, status: utility.operational_status },
    })),
  }), [utilities]);

  if (isLoading) return <LoadingState />;

  const recenter = () => {
    if (nearMeActive && currentLocation) {
      cameraRef.current?.setCamera({
        centerCoordinate: [currentLocation.longitude, currentLocation.latitude],
        zoomLevel: 15,
        animationDuration: 700,
        animationMode: "easeTo",
      });
      return;
    }

    cameraRef.current?.setCamera({
      centerCoordinate: [BRATISLAVA.longitude, BRATISLAVA.latitude],
      zoomLevel: 12,
      animationDuration: 700,
      animationMode: "easeTo",
    });
  };

  const zoom = (direction: "in" | "out") => {
    cameraRef.current?.setCamera({
      zoomLevel: direction === "in" ? 14 : 10,
      animationDuration: 250,
      animationMode: "easeTo",
    });
  };

  const toggleNearMe = () => {
    const next = !nearMeActive;
    setNearMeActive(next);

    if (next && currentLocation) {
      cameraRef.current?.setCamera({
        centerCoordinate: [currentLocation.longitude, currentLocation.latitude],
        zoomLevel: 15,
        animationDuration: 700,
        animationMode: "easeTo",
      });
    }
  };

  return (
    <View style={styles.container}>
      <MapView
        ref={mapRef}
        style={StyleSheet.absoluteFillObject}
        mapStyle={OPEN_FREE_MAP_STYLE}
        compassEnabled={false}
        rotateEnabled={false}
        pitchEnabled={false}
        attributionEnabled
        logoEnabled
        onRegionDidChange={async () => {
          if (!showUtilities) return;
          const [northEast, southWest] = await mapRef.current!.getVisibleBounds();
          setUtilityBounds({
            min_lat: southWest[1], max_lat: northEast[1],
            min_lng: southWest[0], max_lng: northEast[0],
          });
        }}
      >
        <Camera
          ref={cameraRef}
          defaultSettings={{
            centerCoordinate: [BRATISLAVA.longitude, BRATISLAVA.latitude],
            zoomLevel: 12,
            pitch: 0,
            heading: 0,
          }}
          followUserLocation={nearMeActive}
          followUserMode={UserTrackingMode.Follow}
          followZoomLevel={15}
        />

        <UserLocation
          visible={nearMeActive}
          animated
          showsUserHeadingIndicator
          onUpdate={(location) => {
            setCurrentLocation({
              latitude: location.coords.latitude,
              longitude: location.coords.longitude,
            });
          }}
        />

        {!showUtilities && pins.map((event) => {
          const isNearby =
            currentLocation != null &&
            distanceKm(currentLocation, {
              latitude: event.latitude as number,
              longitude: event.longitude as number,
            }) <= NEARBY_RADIUS_KM;

          return (
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
              <View
                style={[
                  styles.annotation,
                  nearMeActive && !isNearby && styles.annotationMuted,
                ]}
              >
                <View
                  style={[
                    styles.annotationInner,
                    isNearby && styles.annotationNearby,
                  ]}
                >
                  <Ionicons name="heart" size={11} color={colors.white} />
                </View>
              </View>
            </PointAnnotation>
          );
        })}

        {showUtilities && <ShapeSource
          id="public-toilets"
          shape={utilityShape}
          cluster
          clusterRadius={48}
          clusterMaxZoomLevel={14}
          onPress={(event) => {
            const feature = event.features[0];
            const id = feature?.properties?.id;
            if (id) router.push({ pathname: "/utility/[id]", params: { id: String(id), kind: "toilet" } });
          }}
        >
          <CircleLayer id="toilet-clusters" filter={["has", "point_count"]} style={{ circleColor: colors.free, circleRadius: 20, circleStrokeColor: colors.white, circleStrokeWidth: 3 }} />
          <SymbolLayer id="toilet-cluster-count" filter={["has", "point_count"]} style={{ textField: ["get", "point_count_abbreviated"], textColor: colors.white, textSize: 11 }} />
          <CircleLayer id="toilet-points" filter={["!", ["has", "point_count"]]} style={{ circleColor: colors.free, circleRadius: 14, circleStrokeColor: colors.white, circleStrokeWidth: 3 }} />
          <SymbolLayer id="toilet-labels" filter={["!", ["has", "point_count"]]} style={{ textField: "WC", textColor: colors.white, textSize: 8, textFont: ["Noto Sans Regular"] }} />
        </ShapeSource>}
      </MapView>

      <View pointerEvents="box-none" style={StyleSheet.absoluteFillObject}>
        <View style={styles.topControls}>
          <View style={styles.searchBar}>
            <Ionicons name="search" size={17} color={colors.primary} />
            <Text style={styles.searchText}>Find events</Text>
          </View>

          <Pressable
            accessibilityLabel={nearMeActive ? "Show all events" : "Show events near me"}
            onPress={toggleNearMe}
            style={[styles.nearButton, nearMeActive && styles.nearButtonActive]}
          >
            <Ionicons
              name="navigate"
              size={17}
              color={nearMeActive ? colors.white : colors.primary}
            />
            <Text
              style={[
                styles.nearText,
                nearMeActive && styles.nearTextActive,
              ]}
            >
              {nearMeActive ? "Nearby" : "Near me"}
            </Text>
          </Pressable>
        </View>

        <View style={styles.countPill}>
          <View style={styles.countDot} />
          <Text style={styles.countText}>
            {nearMeActive
              ? (showUtilities ? utilities.length : nearbyPins.length) + " nearby"
              : (showUtilities ? utilities.length + " toilets" : pins.length + " events")}
          </Text>
        </View>

        <Pressable
          accessibilityLabel={showUtilities ? "Show event map layer" : "Show public toilet map layer"}
          onPress={() => setShowUtilities((current) => !current)}
          style={[styles.layerButton, showUtilities && styles.layerButtonActive]}
        >
          <Ionicons name={showUtilities ? "calendar-outline" : "business-outline"} size={16} color={showUtilities ? colors.white : colors.free} />
          <Text style={[styles.layerText, showUtilities && styles.layerTextActive]}>{showUtilities ? "Events" : "Toilets"}</Text>
        </Pressable>
        <Pressable accessibilityLabel="Browse all city utilities" onPress={() => router.push("/utilities")} style={styles.allUtilitiesButton}>
          <Ionicons name="grid-outline" size={14} color={colors.textMuted} />
          <Text style={styles.allUtilitiesText}>All utilities</Text>
        </Pressable>

        <View style={styles.controls}>
          <Pressable
            accessibilityLabel="Zoom in"
            onPress={() => zoom("in")}
            style={styles.controlButton}
          >
            <Ionicons name="add" size={20} color={colors.text} />
          </Pressable>
          <Pressable
            accessibilityLabel="Zoom out"
            onPress={() => zoom("out")}
            style={styles.controlButton}
          >
            <Ionicons name="remove" size={20} color={colors.text} />
          </Pressable>
          <Pressable
            accessibilityLabel="Recenter map"
            onPress={recenter}
            style={styles.controlButton}
          >
            <Ionicons name="locate" size={19} color={colors.primary} />
          </Pressable>
        </View>

        <View style={styles.statusPill}>
          <Ionicons
            name={nearMeActive ? "navigate" : "map-outline"}
            size={13}
            color={colors.primary}
          />
          <Text style={styles.statusText}>
            {nearMeActive
              ? (showUtilities ? utilities.length : nearbyPins.length)
                ? (showUtilities ? utilities.length + " public toilets near you" : nearbyPins.length + " events near you")
                : showUtilities ? "No nearby public toilets" : "No nearby events"
              : showUtilities
                ? utilities.length ? utilities.length + " public toilets in this area" : "No public toilets in this area"
              : pins.length
                ? pins.length + " events on the map"
                : "No mapped events yet"}
          </Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.mapWater,
  },
  topControls: {
    marginTop: 16,
    marginHorizontal: 16,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  searchBar: {
    flex: 1,
    height: 46,
    borderRadius: 16,
    paddingHorizontal: 14,
    backgroundColor: "rgba(255,255,255,0.96)",
    flexDirection: "row",
    alignItems: "center",
    gap: 9,
    borderWidth: 1,
    borderColor: colors.border,
    shadowColor: colors.shadow,
    shadowOpacity: 0.1,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
  },
  searchText: {
    color: colors.textMuted,
    fontFamily: fonts.medium,
    fontSize: 11,
  },
  nearButton: {
    height: 46,
    borderRadius: 16,
    paddingHorizontal: 13,
    backgroundColor: "rgba(255,255,255,0.96)",
    borderWidth: 1,
    borderColor: colors.border,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    shadowColor: colors.shadow,
    shadowOpacity: 0.1,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
  },
  nearButtonActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  nearText: {
    color: colors.text,
    fontFamily: fonts.semibold,
    fontSize: 10,
  },
  nearTextActive: {
    color: colors.white,
  },
  countPill: {
    alignSelf: "flex-start",
    marginTop: 8,
    marginLeft: 18,
    height: 26,
    paddingHorizontal: 10,
    borderRadius: 13,
    backgroundColor: "rgba(39,35,41,0.9)",
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
  },
  countDot: {
    width: 5,
    height: 5,
    borderRadius: 3,
    backgroundColor: colors.primary,
  },
  countText: {
    color: colors.white,
    fontFamily: fonts.medium,
    fontSize: 8,
  },
  layerButton: {
    alignSelf: "flex-start",
    marginTop: 8,
    marginLeft: 18,
    height: 34,
    paddingHorizontal: 12,
    borderRadius: 17,
    backgroundColor: "rgba(255,255,255,0.96)",
    borderWidth: 1,
    borderColor: colors.border,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  allUtilitiesButton: {
    alignSelf: "flex-start",
    marginTop: 6,
    marginLeft: 18,
    height: 32,
    paddingHorizontal: 11,
    borderRadius: 16,
    backgroundColor: "rgba(255,255,255,0.96)",
    borderWidth: 1,
    borderColor: colors.border,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  allUtilitiesText: { color: colors.textMuted, fontFamily: fonts.semibold, fontSize: 9 },
  layerButtonActive: { backgroundColor: colors.free, borderColor: colors.free },
  layerText: { color: colors.text, fontFamily: fonts.semibold, fontSize: 10 },
  layerTextActive: { color: colors.white },
  controls: {
    position: "absolute",
    right: 16,
    bottom: 174,
    gap: 7,
  },
  controlButton: {
    width: 42,
    height: 42,
    borderRadius: 15,
    backgroundColor: "rgba(255,255,255,0.96)",
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: colors.shadow,
    shadowOpacity: 0.12,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
  },
  annotation: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
  },
  annotationMuted: {
    opacity: 0.28,
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
  annotationNearby: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.primaryDark,
  },
  statusPill: {
    position: "absolute",
    left: 18,
    right: 18,
    bottom: 104,
    alignSelf: "center",
    minHeight: 34,
    paddingHorizontal: 12,
    borderRadius: 17,
    backgroundColor: "rgba(255,255,255,0.94)",
    borderWidth: 1,
    borderColor: colors.border,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
  },
  statusText: {
    color: colors.textMuted,
    fontFamily: fonts.medium,
    fontSize: 10,
  },
});
