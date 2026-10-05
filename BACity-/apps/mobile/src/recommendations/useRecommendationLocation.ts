import AsyncStorage from "@react-native-async-storage/async-storage";
import * as Location from "expo-location";
import { Linking } from "react-native";
import { useCallback, useEffect, useRef, useState } from "react";
import { getSessionRevision } from "../store/tokenSession";
import { coarsenCoordinates, deniedPermissionState, isWithinRecommendationArea, locationFailureState, shouldRequestPermission } from "./locationPolicy";

const PREFERENCE_KEY = "bacity.recommendations.use-location.v1";
const LOCATION_TIMEOUT_MS = 15_000;
const LAST_KNOWN_MAX_AGE_MS = 10 * 60_000;
const LAST_KNOWN_REQUIRED_ACCURACY_METERS = 2_000;

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
  | "timeout"
  | "error";

export type RecommendationCoordinates = { latitude: number; longitude: number };

class LocationTimeoutError extends Error {
  code = "BACITY_LOCATION_TIMEOUT";

  constructor() {
    super("Timed out waiting for a foreground location fix");
    this.name = "LocationTimeoutError";
  }
}

function developmentLocationLog(stage: string, error?: unknown, details?: Record<string, boolean>) {
  if (!__DEV__) return;
  const value = typeof error === "object" && error !== null ? error as { code?: unknown; name?: unknown } : null;
  console.warn("[recommendations/location]", {
    stage,
    errorCode: value?.code ? String(value.code) : undefined,
    errorName: value?.name ? String(value.name) : typeof error,
    ...details,
  });
}

async function currentCoarseLocation(): Promise<RecommendationCoordinates> {
  const lastKnown = await Location.getLastKnownPositionAsync({
    maxAge: LAST_KNOWN_MAX_AGE_MS,
    requiredAccuracy: LAST_KNOWN_REQUIRED_ACCURACY_METERS,
  });
  if (lastKnown) {
    return coarsenCoordinates(lastKnown.coords.latitude, lastKnown.coords.longitude);
  }

  let timeout: ReturnType<typeof setTimeout> | undefined;
  try {
    const position = await Promise.race([
      Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
        mayShowUserSettingsDialog: true,
      }),
      new Promise<never>((_, reject) => {
        timeout = setTimeout(() => reject(new LocationTimeoutError()), LOCATION_TIMEOUT_MS);
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
  const acquisition = useRef(0);
  const activeRef = useRef(active);
  activeRef.current = active;

  const locateWithPermission = useCallback(async () => {
    const attempt = ++acquisition.current;
    const session = getSessionRevision();
    const current = () => activeRef.current && acquisition.current === attempt && session === getSessionRevision();
    setStatus("locating");
    try {
      const provider = await Location.getProviderStatusAsync();
      if (!current()) return;
      if (!provider.locationServicesEnabled) {
        setCoordinates(null);
        setStatus("unavailable");
        developmentLocationLog("provider-unavailable", undefined, {
          locationServicesEnabled: provider.locationServicesEnabled,
          gpsAvailable: provider.gpsAvailable ?? false,
          networkAvailable: provider.networkAvailable ?? false,
        });
        return;
      }
      const position = await currentCoarseLocation();
      if (!current()) return;
      if (!isWithinRecommendationArea(position.latitude, position.longitude)) {
        setCoordinates(null);
        setStatus("outside-area");
        return;
      }
      setCoordinates(position);
      setStatus("granted");
    } catch (error) {
      if (!current()) return;
      setCoordinates(null);
      const failure = locationFailureState(error);
      setStatus(failure);
      developmentLocationLog("acquisition-failed", error);
    }
  }, []);

  useEffect(() => {
    if (!active) {
      acquisition.current += 1;
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
      } catch (error) {
        if (mounted) {
          setStatus(locationFailureState(error));
          developmentLocationLog("preference-restore-failed", error);
        }
      }
    })();
    return () => { mounted = false; acquisition.current += 1; };
  }, [active, locateWithPermission]);

  const enable = useCallback(async () => {
    if (!activeRef.current) return;
    const attempt = ++acquisition.current;
    const session = getSessionRevision();
    const current = () => activeRef.current && acquisition.current === attempt && session === getSessionRevision();
    setEnabled(true);
    await AsyncStorage.setItem(PREFERENCE_KEY, "true");
    try {
      let permission = await Location.getForegroundPermissionsAsync();
      if (!current()) return;
      if (shouldRequestPermission(true, true, permission)) {
        permission = await Location.requestForegroundPermissionsAsync();
      }
      if (!current()) return;
      if (!permission.granted) {
        setCoordinates(null);
        setStatus(deniedPermissionState(permission));
        return;
      }
      await locateWithPermission();
    } catch (error) {
      if (!current()) return;
      setCoordinates(null);
      setStatus(locationFailureState(error));
      developmentLocationLog("permission-or-acquisition-failed", error);
    }
  }, [locateWithPermission]);

  const disable = useCallback(async () => {
    acquisition.current += 1;
    setEnabled(false);
    setCoordinates(null);
    setStatus("disabled");
    await AsyncStorage.setItem(PREFERENCE_KEY, "false");
  }, []);

  return {
    enabled,
    status,
    coordinates: active && enabled ? coordinates : null,
    enable,
    disable,
    retry: enable,
    openSettings: () => Linking.openSettings(),
  };
}
