/**
 * Thin fetch wrapper around the FastAPI backend (services/api).
 *
 * Base URL comes from EXPO_PUBLIC_API_URL so it can point at:
 *   - http://localhost:8000        (iOS simulator)
 *   - http://10.0.2.2:8000         (Android emulator)
 *   - http://<your-lan-ip>:8000    (physical device on the same network)
 *   - a deployed API origin in production
 *
 * See .env.example at the mobile app root.
 */
import { useAuthStore } from "../store/authStore";

const API_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  auth?: boolean; // attach Bearer token if the user is logged in
  params?: Record<string, string | number | boolean | undefined>;
}

function buildQuery(params?: RequestOptions["params"]): string {
  if (!params) return "";
  const usable = Object.entries(params).filter(([, v]) => v !== undefined && v !== "");
  if (usable.length === 0) return "";
  const search = new URLSearchParams(
    usable.map(([k, v]) => [k, String(v)])
  );
  return `?${search.toString()}`;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = false, params } = options;

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (auth) {
    const token = useAuthStore.getState().token;
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}${buildQuery(params)}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const errBody = await res.json();
      detail = errBody.detail ?? detail;
    } catch {
      // response wasn't JSON — keep statusText
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}