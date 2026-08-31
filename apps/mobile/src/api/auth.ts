import { apiRequest } from "./client";

export interface UserOut {
  id: string;
  email: string;
  display_name: string | null;
  interests: string[];
}

interface TokenResponse {
  access_token: string;
  token_type: string;
}

export function register(email: string, password: string, display_name?: string): Promise<UserOut> {
  return apiRequest<UserOut>("/auth/register", { method: "POST", body: { email, password, display_name } });
}

export function login(email: string, password: string): Promise<TokenResponse> {
  return apiRequest<TokenResponse>("/auth/login", { method: "POST", body: { email, password } });
}

export function getMe(): Promise<UserOut> {
  return apiRequest<UserOut>("/users/me", { auth: true });
}

export function updateInterests(interests: string[]): Promise<UserOut> {
  return apiRequest<UserOut>("/users/me", { method: "PATCH", auth: true, body: { interests } });
}