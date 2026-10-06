/** Release entry only after the current account's Home route is acknowledged. */
export function entryDestination(owner: string | null, currentOwner: string | null, pathname: string) {
  if (!owner || owner !== currentOwner) return 'ignore';
  return pathname === '/discover' || pathname === '/(tabs)/discover' ? 'complete' : 'home';
}
