let sessionToken: string | null = null;
let sessionRevision = 0;

export function getSessionRevision(): number {
  return sessionRevision;
}

export function getSessionToken(): string | null {
  return sessionToken;
}

export function setSessionToken(token: string | null): void {
  if (token !== sessionToken) sessionRevision += 1;
  sessionToken = token;
}
