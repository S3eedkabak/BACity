/** Auth entry resolves to Home; restoring a session preserves a valid destination. */
export function entryDestination(owner: string | null, currentOwner: string | null, pathname: string) {
  if (!owner || owner !== currentOwner) return 'ignore';
  return ['/', '/auth', '/oauth', '/welcome'].includes(pathname) ? 'home' : 'complete';
}
