/** Pure lifecycle policy; no authentication, navigation, timers or API side effects. */
export function entryPlayback(reduced: boolean | null, failed: boolean, foreground: boolean) {
  if (!foreground || reduced === null) return 'hold';
  return reduced || failed ? 'static' : 'video';
}
export function visibleWait(busy: boolean, revealed: boolean, entryActive: boolean, dismissed: boolean) {
  return busy && revealed && !entryActive && !dismissed;
}
export function substantialWait(allowed: boolean, pending: boolean, hasContent: boolean) {
  return allowed && pending && !hasContent;
}
