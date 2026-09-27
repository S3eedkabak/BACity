import AsyncStorage from "@react-native-async-storage/async-storage";
import * as Location from "expo-location";
import { Linking } from "react-native";
import { useCallback, useEffect, useState } from "react";
import { coarsenCoordinates, deniedPermissionState, isWithinRecommendationArea, shouldRequestPermission } from "./locationPolicy";

const PREFERENCE_KEY = "bacity.recommendations.use-location.v1";
const LOCATION_TIMEOUT_MS = 8_000;

export type RecommendationLocationStatus =
  | "loading"
  | "not-requested"
  | "disabled"
  | "locating"
  | "granted"
  | "denied"
  | "blocked"
  | "outside-area"
  | "unavailable"
  | "error";

export type RecommendationCoordinates = { latitude: number; longitude: number };

async function currentCoarseLocation(): Promise<RecommendationCoordinates> {
  let timeout: ReturnType<typeof setTimeout> | undefined;
  try {
    const position = await Promise.race([
      Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }),
      new Promise<never>((_, reject) => {
        timeout = setTimeout(() => reject(new Error("Location request timed out")), LOCATION_TIMEOUT_MS);
      }),
    ]);
    return coarsenCoordinates(position.coords.latitude, position.coords.longitude);
  } finally {
    if (timeout) clearTimeout(timeout);
  }
}

export function useRecommendationLocation(active = true) {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [status, setStatus] = useState<RecommendationLocationStatus>("loading");
  const [coordinates, setCoordinates] = useState<RecommendationCoordinates | null>(null);

  const locateWithPermission = useCallback(async () => {
    setStatus("locating");
    try {
      if (!(await Location.hasServicesEnabledAsync())) {
        setCoordinates(null);
        setStatus("unavailable");
        return;
      }
      const current = await currentCoarseLocation();
      if (!isWithinRecommendationArea(current.latitude, current.longitude)) {
        setCoordinates(null);
        setStatus("outside-area");
        return;
      }
      setCoordinates(current);
      setStatus("granted");
    } catch {
      setCoordinates(null);
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    if (!active) {
      setCoordinates(null);
      setEnabled(null);
      setStatus("loading");
      return;
    }
    let mounted = true;
    void (async () => {
      try {
        const stored = await AsyncStorage.getItem(PREFERENCE_KEY);
        if (!mounted) return;
        if (stored === null) {
          setEnabled(null);
          setStatus("not-requested");
          return;
        }
        const useLocation = stored === "true";
        setEnabled(useLocation);
        if (!useLocation) {
          setStatus("disabled");
          return;
        }
        const permission = await Location.getForegroundPermissionsAsync();
        if (!mounted) return;
        if (permission.granted) {
          await locateWithPermission();
        } else {
          setStatus(deniedPermissionState(permission));
        }
      } catch {
        if (mounted) setStatus("error");
      }
    })();
    return () => { mounted = false; };
  }, [active, locateWithPermission]);

  const enable = useCallback(async () => {
    setEnabled(true);
    await AsyncStorage.setItem(PREFERENCE_KEY, "true");
    try {
      let permission = await Location.getForegroundPermissionsAsync();
      if (shouldRequestPermission(true, true, permission)) {
        permission = await Location.requestForegroundPermissionsAsync();
      }
      if (!permission.granted) {
        setCoordinates(null);
        setStatus(deniedPermissionState(permission));
        return;
      }
      await locateWithPermission();
    } catch {
      setCoordinates(null);
      setStatus("error");
    }
  }, [locateWithPermission]);

  const disable = useCallback(async () => {
    setEnabled(false);
    setCoordinates(null);
    setStatus("disabled");
    await AsyncStorage.setItem(PREFERENCE_KEY, "false");
  }, []);

  return {
    enabled,
    status,
    coordinates: enabled ? coordinates : null,
    enable,
    disable,
    retry: enable,
    openSettings: () => Linking.openSettings(),
  };
}
