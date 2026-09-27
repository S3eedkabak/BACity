export type PermissionLike = { granted: boolean; canAskAgain: boolean };

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
