export type ApiPlatform = "android" | "ios" | "web" | string;

const ANDROID_EMULATOR_HOST = /^(https?:\/\/)10\.0\.2\.2(?=[:/]|$)/i;
const LOCALHOST = /^(https?:\/\/)(?:localhost|127\.0\.0\.1)(?=[:/]|$)/i;

/**
 * Resolve only local loopback aliases. LAN, staging, and production URLs are
 * returned unchanged.
 */
export function resolveApiUrl(configuredUrl: string | undefined, platform: ApiPlatform): string {
  const fallback = platform === "android"
    ? "http://10.0.2.2:8000"
    : "http://localhost:8000";
  const apiUrl = configuredUrl?.trim() || fallback;

  if (platform === "android") {
    return apiUrl.replace(LOCALHOST, (_match, scheme: string) => `${scheme}10.0.2.2`);
  }

  if (platform === "web" || platform === "ios") {
    return apiUrl.replace(ANDROID_EMULATOR_HOST, (_match, scheme: string) => `${scheme}localhost`);
  }

  return apiUrl;
}
