/**
 * Thin fetch wrapper around the FastAPI backend.
 *
 * Auth tokens live in tokenSession.ts rather than importing the Zustand
 * auth store here. This intentionally removes the client -> store -> auth
 * -> client circular dependency.
 */
import { getSessionToken } from "../store/tokenSession";

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
  auth?: boolean;
  params?: Record<string, string | number | boolean | undefined>;
}

function buildQuery(params?: RequestOptions["params"]): string {
  if (!params) return "";
  const usable = Object.entries(params).filter(([, value]) => value !== undefined && value !== "");
  if (usable.length === 0) return "";
  const search = new URLSearchParams(usable.map(([key, value]) => [key, String(value)]));
  return `?${search.toString()}`;
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const { method = "GET", body, auth = false, params } = options;

  const headers: Record<string, string> = { "Content-Type": "application/json" };

  if (auth) {
    const token = getSessionToken();
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
      // Keep the HTTP status text when the body is not JSON.
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
