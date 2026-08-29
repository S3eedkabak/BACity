/**
 * Map screen (spec section 41). Plots events that have coordinates on a
 * MapView centered on Bratislava; tapping a marker's callout opens the
 * event detail screen.
 *
 * NOTE: react-native-maps needs a native build to run (EAS build, or
 * `npx expo run:ios` / `run:android`) — it is not available inside the
 * plain Expo Go sandbox app. See apps/mobile/README.md.
 */
import { useMemo } from "react";
import { StyleSheet, View } from "react-native";
import MapView, { Marker, PROVIDER_GOOGLE } from "react-native-maps";
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

  const pins = useMemo(
    () => (data?.items ?? []).filter((e) => e.latitude != null && e.longitude != null),
    [data]
  );

  if (isLoading) return <LoadingState />;

  return (
    <View style={styles.container}>
      <MapView
        style={StyleSheet.absoluteFill}
        provider={PROVIDER_GOOGLE}
        initialRegion={BRATISLAVA_REGION}
      >
        {pins.map((event) => (
          <Marker
            key={event.id}
            coordinate={{ latitude: event.latitude as number, longitude: event.longitude as number }}
            title={event.title}
            description={event.venue?.name ?? event.address ?? undefined}
            pinColor={colors.primary}
            onCalloutPress={() => router.push(`/event/${event.id}`)}
          />
        ))}
      </MapView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
});