export type PermissionLike = { granted: boolean; canAskAgain: boolean };

export type LocationFailureState = "timeout" | "unavailable" | "error";

export function coarsenCoordinates(latitude: number, longitude: number) {
  return {
    latitude: Number(latitude.toFixed(3)),
    longitude: Number(longitude.toFixed(3)),
  };
}

export function deniedPermissionState(permission: PermissionLike): "denied" | "blocked" {
  return permission.canAskAgain ? "denied" : "blocked";
}

export function isWithinRecommendationArea(latitude: number, longitude: number) {
  return latitude >= 48 && latitude <= 48.35 && longitude >= 16.9 && longitude <= 17.35;
}

export function shouldRequestPermission(
  enabled: boolean,
  userInitiated: boolean,
  permission: PermissionLike
) {
  return enabled && userInitiated && !permission.granted && permission.canAskAgain;
}

export function locationFailureState(error: unknown): LocationFailureState {
  const code = typeof error === "object" && error !== null && "code" in error
    ? String(error.code)
    : "";
  if (code === "BACITY_LOCATION_TIMEOUT") return "timeout";
  if (["E_LOCATION_SERVICES_DISABLED", "E_LOCATION_SETTINGS_UNSATISFIED", "E_LOCATION_UNAVAILABLE"].includes(code)) {
    return "unavailable";
  }
  return "error";
}
