/** Keep authenticated React Query data isolated across account changes. */
export function accountQueryKey(resource: string, userId: string | null | undefined, ...parts: unknown[]) {
  return [resource, userId ?? "signed-out", ...parts] as const;
}
