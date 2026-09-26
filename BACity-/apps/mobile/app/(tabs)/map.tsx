import { Ionicons } from "@expo/vector-icons";
import type {
  CameraRef,
  MapViewRef,
  ShapeSourceRef,
} from "@maplibre/maplibre-react-native";
import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ActivityIndicator, Platform, Pressable, StyleSheet, Text, View } from "react-native";
import { useEvents } from "../../src/hooks/useEvents";
import { colors } from "../../src/theme/colors";
import { fonts } from "../../src/theme/fonts";
import { nearbyUtilities, utilitiesInViewport, type UtilityBounds } from "../../src/api/utilities";
import type { EventOut } from "../../src/types/event";
import type { Utility } from "../../src/api/utilities";
import {
  boundsKey,
  containsBounds,
  expandAndSnapBounds,
  loadMapSnapshot,
  mergeViewportUtilities,
  updateMapSnapshot,
} from "../../src/map/mapCache";
import {
  buildEventFeatureCollection,
  hasValidMapCoordinates,
} from "../../src/map/eventGeoJson";

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
  ShapeSource,
  SymbolLayer,
  UserLocation,
  UserTrackingMode,
  OfflineManager,
} = nativeMapLibre ?? ({} as typeof import("@maplibre/maplibre-react-native"));

const BRATISLAVA = {
  longitude: 17.1077,
  latitude: 48.1486,
};

const OPEN_FREE_MAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";
const NEARBY_RADIUS_KM = 3;
const INITIAL_VIEWPORT: UtilityBounds = {
  min_lat: 48.105,
  max_lat: 48.205,
  min_lng: 17.035,
  max_lng: 17.185,
};
const INITIAL_BOUNDS = expandAndSnapBounds(INITIAL_VIEWPORT);
const MAP_DATA_STALE_MS = 5 * 60_000;
const MAP_QUERY_GC_MS = 30 * 60_000;
const AMBIENT_TILE_CACHE_BYTES = 75 * 1024 * 1024;
let ambientCacheConfigured = false;

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
  const eventsQuery = useEvents({ limit: 100 });
  const cameraRef = useRef<CameraRef>(null);
  const mapRef = useRef<MapViewRef>(null);
  const eventSourceRef = useRef<ShapeSourceRef>(null);
  const utilitySourceRef = useRef<ShapeSourceRef>(null);
  const requestedBoundsRef = useRef(INITIAL_BOUNDS);
  const [nearMeActive, setNearMeActive] = useState(false);
  const [showUtilities, setShowUtilities] = useState(false);
  const [utilityBounds, setUtilityBounds] = useState(INITIAL_BOUNDS);
  const [cachedEvents, setCachedEvents] = useState<EventOut[]>([]);
  const [cachedUtilities, setCachedUtilities] = useState<Utility[]>([]);
  const [cacheSavedAt, setCacheSavedAt] = useState(0);
  const [basemapUnavailable, setBasemapUnavailable] = useState(false);
  const [mapReady, setMapReady] = useState(false);
  const [currentLocation, setCurrentLocation] = useState<Coordinates | null>(
    null
  );

  useEffect(() => {
    let active = true;
    void loadMapSnapshot().then((snapshot) => {
      if (!active) return;
      setCachedEvents(snapshot.events);
      setCachedUtilities(snapshot.utilities);
      setCacheSavedAt(snapshot.savedAt);
    });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!eventsQuery.data) return;
    setCachedEvents(eventsQuery.data.items);
    const snapshot = updateMapSnapshot({ events: eventsQuery.data.items });
    setCacheSavedAt(snapshot.savedAt);
  }, [eventsQuery.data]);

  useEffect(() => {
    if (ambientCacheConfigured || !OfflineManager) return;
    ambientCacheConfigured = true;
    void OfflineManager.setMaximumAmbientCacheSize(AMBIENT_TILE_CACHE_BYTES).catch(() => {
      ambientCacheConfigured = false;
    });
  }, []);

  const eventItems = eventsQuery.data?.items ?? cachedEvents;

  const pins = useMemo(
    () => eventItems.filter(hasValidMapCoordinates),
    [eventItems]
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

  const roundedLocation = useMemo(() => currentLocation ? {
    latitude: Number(currentLocation.latitude.toFixed(3)),
    longitude: Number(currentLocation.longitude.toFixed(3)),
  } : null, [currentLocation]);

  const utilityViewport = useQuery({
    queryKey: ["map-utilities-viewport", boundsKey(utilityBounds)],
    queryFn: () => utilitiesInViewport(utilityBounds),
    enabled: showUtilities && !nearMeActive,
    staleTime: MAP_DATA_STALE_MS,
    gcTime: MAP_QUERY_GC_MS,
    placeholderData: (previous) => previous,
    refetchOnWindowFocus: false,
  });
  const utilityNearby = useQuery({
    queryKey: ["map-utilities-nearby", roundedLocation?.latitude, roundedLocation?.longitude, NEARBY_RADIUS_KM],
    queryFn: () => nearbyUtilities(roundedLocation!.latitude, roundedLocation!.longitude, NEARBY_RADIUS_KM),
    enabled: showUtilities && nearMeActive && roundedLocation != null,
    staleTime: 2 * 60_000,
    gcTime: MAP_QUERY_GC_MS,
    placeholderData: (previous) => previous,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (!utilityViewport.data || utilityViewport.isPlaceholderData) return;
    setCachedUtilities((current) => {
      const merged = mergeViewportUtilities(current, utilityViewport.data, utilityBounds);
      const snapshot = updateMapSnapshot({ utilities: merged });
      setCacheSavedAt(snapshot.savedAt);
      return merged;
    });
  }, [utilityBounds, utilityViewport.data, utilityViewport.isPlaceholderData]);

  useEffect(() => {
    if (!utilityNearby.data || utilityNearby.isPlaceholderData) return;
    setCachedUtilities((current) => {
      const mergedById = new Map(current.map((item) => [item.id, item]));
      for (const item of utilityNearby.data) mergedById.set(item.id, item);
      const merged = Array.from(mergedById.values()).slice(-1_000);
      const snapshot = updateMapSnapshot({ utilities: merged });
      setCacheSavedAt(snapshot.savedAt);
      return merged;
    });
  }, [utilityNearby.data, utilityNearby.isPlaceholderData]);

  const cachedNearbyUtilities = useMemo(() => roundedLocation
    ? cachedUtilities.filter((utility) => distanceKm(roundedLocation, utility) <= NEARBY_RADIUS_KM)
    : [], [cachedUtilities, roundedLocation]);
  const utilities = nearMeActive
    ? utilityNearby.data ?? cachedNearbyUtilities
    : cachedUtilities.length ? cachedUtilities : utilityViewport.data ?? [];

  const eventShape = useMemo(
    () => buildEventFeatureCollection(
      pins,
      (event) => currentLocation != null && distanceKm(currentLocation, event) <= NEARBY_RADIUS_KM,
    ),
    [currentLocation, pins],
  );

  useEffect(() => {
    if (!__DEV__ || !mapReady || showUtilities || eventShape.features.length === 0) return;
    const timer = setTimeout(() => {
      void (async () => {
        try {
          const source = await eventSourceRef.current?.features();
          const sourceFeatureCount = source?.features.length ?? 0;
          const diagnostics = {
            geoJsonFeatures: eventShape.features.length,
            sourceFeatures: sourceFeatureCount,
            firstCoordinates: eventShape.features[0]?.geometry.coordinates,
          };
          if (sourceFeatureCount === 0) {
            console.error("[map:event-layer] populated GeoJSON produced an empty native source", diagnostics);
          } else {
            console.info("[map:event-layer] verified", diagnostics);
          }
        } catch (error) {
          console.warn("[map:event-layer] inspection failed", error);
        }
      })();
    }, 2_000);
    return () => clearTimeout(timer);
  }, [eventShape, mapReady, showUtilities]);

  const utilityShape = useMemo(() => ({
    type: "FeatureCollection" as const,
    features: utilities.map((utility) => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [utility.longitude, utility.latitude] },
      properties: { id: utility.id, kind: utility.kind, name: utility.name, status: utility.operational_status },
    })),
  }), [utilities]);

  const activeUtilityQuery = nearMeActive ? utilityNearby : utilityViewport;
  const isRefreshing = showUtilities ? activeUtilityQuery.isFetching : eventsQuery.isFetching;
  const dataUnavailable = showUtilities ? activeUtilityQuery.isError : eventsQuery.isError;
  const hasCachedLayer = showUtilities ? utilities.length > 0 : pins.length > 0;
  const cacheIsOld = cacheSavedAt > 0 && Date.now() - cacheSavedAt > MAP_DATA_STALE_MS;

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

  const handleRegionDidChange = useCallback(async () => {
    if (!showUtilities || nearMeActive || !mapRef.current) return;
    try {
      const [northEast, southWest] = await mapRef.current.getVisibleBounds();
      const visibleBounds: UtilityBounds = {
        min_lat: southWest[1], max_lat: northEast[1],
        min_lng: southWest[0], max_lng: northEast[0],
      };
      if (containsBounds(requestedBoundsRef.current, visibleBounds)) return;
      const nextBounds = expandAndSnapBounds(visibleBounds);
      if (boundsKey(nextBounds) === boundsKey(requestedBoundsRef.current)) return;
      requestedBoundsRef.current = nextBounds;
      setUtilityBounds(nextBounds);
    } catch {
      // A camera can disappear while an async native bounds request is resolving.
    }
  }, [nearMeActive, showUtilities]);

  const toggleLayer = useCallback(async () => {
    if (showUtilities) {
      setShowUtilities(false);
      return;
    }
    if (!nearMeActive && mapRef.current) {
      try {
        const [northEast, southWest] = await mapRef.current.getVisibleBounds();
        const nextBounds = expandAndSnapBounds({
          min_lat: southWest[1], max_lat: northEast[1],
          min_lng: southWest[0], max_lng: northEast[0],
        });
        requestedBoundsRef.current = nextBounds;
        setUtilityBounds(nextBounds);
      } catch {
        // Fall back to the last useful viewport while the native map settles.
      }
    }
    setShowUtilities(true);
  }, [nearMeActive, showUtilities]);

  const expandCluster = useCallback(async (
    feature: GeoJSON.Feature,
    sourceRef: React.RefObject<ShapeSourceRef>,
  ) => {
    try {
      if (feature.geometry.type !== "Point" || !sourceRef.current) return;
      const zoomLevel = await sourceRef.current.getClusterExpansionZoom(feature);
      cameraRef.current?.setCamera({
        centerCoordinate: feature.geometry.coordinates as [number, number],
        zoomLevel,
        animationDuration: 280,
        animationMode: "easeTo",
      });
    } catch {
      // The source can be replaced while the native cluster query is resolving.
    }
  }, []);

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
        regionDidChangeDebounceTime={700}
        onRegionDidChange={handleRegionDidChange}
        onDidFinishLoadingMap={() => {
          setBasemapUnavailable(false);
          setMapReady(true);
        }}
        onDidFailLoadingMap={() => {
          setBasemapUnavailable(true);
          setMapReady(false);
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
            const next = {
              latitude: location.coords.latitude,
              longitude: location.coords.longitude,
            };
            setCurrentLocation((current) =>
              !current || distanceKm(current, next) >= 0.05 ? next : current
            );
          }}
        />

        {!showUtilities && <ShapeSource
          ref={eventSourceRef}
          id="map-events"
          shape={eventShape}
          cluster
          clusterRadius={52}
          clusterMaxZoomLevel={13}
          hitbox={{ width: 46, height: 46 }}
          onPress={(event) => {
            const feature = event.features[0];
            if (!feature) return;
            if (feature.properties?.point_count) {
              void expandCluster(feature, eventSourceRef);
              return;
            }
            const id = feature.properties?.id;
            if (id) router.push("/event/" + String(id));
          }}
        >
          <CircleLayer id="event-clusters" aboveLayerID="label_country_1" filter={["has", "point_count"]} style={{ circleColor: colors.primaryDark, circleRadius: 21, circleStrokeColor: colors.white, circleStrokeWidth: 3 }} />
          <SymbolLayer id="event-cluster-count" aboveLayerID="event-clusters" filter={["has", "point_count"]} style={{ textField: ["get", "point_count_abbreviated"], textColor: colors.white, textSize: 11, textFont: ["Noto Sans Regular"] }} />
          <CircleLayer id="event-points" aboveLayerID="event-cluster-count" filter={["!", ["has", "point_count"]]} style={{
            circleColor: ["case", ["==", ["get", "nearby"], true], colors.primaryDark, colors.primary],
            circleOpacity: nearMeActive ? ["case", ["==", ["get", "nearby"], true], 1, 0.3] : 1,
            circleRadius: ["case", ["==", ["get", "nearby"], true], 16, 14],
            circleStrokeColor: colors.white,
            circleStrokeWidth: 3,
          }} />
          <SymbolLayer id="event-symbols" aboveLayerID="event-points" filter={["!", ["has", "point_count"]]} style={{
            textField: "♥",
            textColor: colors.white,
            textSize: 10,
            textFont: ["Noto Sans Regular"],
            textOpacity: nearMeActive ? ["case", ["==", ["get", "nearby"], true], 1, 0.45] : 1,
          }} />
        </ShapeSource>}

        {showUtilities && <ShapeSource
          ref={utilitySourceRef}
          id="public-toilets"
          shape={utilityShape}
          cluster
          clusterRadius={48}
          clusterMaxZoomLevel={14}
          onPress={(event) => {
            const feature = event.features[0];
            if (!feature) return;
            if (feature.properties?.point_count) {
              void expandCluster(feature, utilitySourceRef);
              return;
            }
            const id = feature?.properties?.id;
            if (id) router.push({ pathname: "/utility/[id]", params: { id: String(id), kind: String(feature.properties?.kind ?? "toilet") } });
          }}
        >
          <CircleLayer id="toilet-clusters" aboveLayerID="label_country_1" filter={["has", "point_count"]} style={{ circleColor: colors.free, circleRadius: 20, circleStrokeColor: colors.white, circleStrokeWidth: 3 }} />
          <SymbolLayer id="toilet-cluster-count" aboveLayerID="toilet-clusters" filter={["has", "point_count"]} style={{ textField: ["get", "point_count_abbreviated"], textColor: colors.white, textSize: 11, textFont: ["Noto Sans Regular"] }} />
          <CircleLayer id="toilet-points" aboveLayerID="toilet-cluster-count" filter={["!", ["has", "point_count"]]} style={{ circleColor: colors.free, circleRadius: 14, circleStrokeColor: colors.white, circleStrokeWidth: 3 }} />
          <SymbolLayer id="toilet-labels" aboveLayerID="toilet-points" filter={["!", ["has", "point_count"]]} style={{ textField: "WC", textColor: colors.white, textSize: 8, textFont: ["Noto Sans Regular"] }} />
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
          {isRefreshing && <ActivityIndicator size={9} color={colors.white} />}
        </View>

        <Pressable
          accessibilityLabel={showUtilities ? "Show event map layer" : "Show public toilet map layer"}
          onPress={() => { void toggleLayer(); }}
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
            name={dataUnavailable || basemapUnavailable ? "cloud-offline-outline" : nearMeActive ? "navigate" : "map-outline"}
            size={13}
            color={dataUnavailable || basemapUnavailable ? colors.textMuted : colors.primary}
          />
          <Text style={styles.statusText}>
            {basemapUnavailable
              ? "Basemap network unavailable · cached tiles may remain visible"
              : dataUnavailable && hasCachedLayer
                ? `Offline · showing ${cacheIsOld ? "saved" : "cached"} ${showUtilities ? "utilities" : "events"}`
                : dataUnavailable
                  ? `Unable to refresh ${showUtilities ? "utilities" : "events"}`
                  : isRefreshing && !hasCachedLayer
                    ? `Loading ${showUtilities ? "utilities" : "events"}…`
                  : nearMeActive
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
