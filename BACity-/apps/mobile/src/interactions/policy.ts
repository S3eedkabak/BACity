/** Local UX policy. Authentication and persisted values remain server-authoritative. */
export type ActionState = 'idle' | 'loading' | 'success' | 'error';
export const reviewDimensions = {
  event: ['worth_attending', 'crowd', 'value', 'accessibility', 'would_attend_again'],
  place: ['atmosphere', 'price', 'accessibility', 'cleanliness', 'crowdedness', 'family_friendliness', 'solo_friendliness'],
} as const;
export function reviewError(kind: keyof typeof reviewDimensions, body: string, ratings: Record<string, number>) {
  if (body.trim().length < 10 || body.length > 3000) return 'Write between 10 and 3,000 characters.';
  const entries = Object.entries(ratings);
  if (!entries.length) return 'Rate at least one aspect you experienced.';
  if (entries.some(([key, value]) => !(reviewDimensions[kind] as readonly string[]).includes(key) || !Number.isInteger(value) || value < 1 || value > 5)) return 'Choose ratings from 1 to 5.';
  return '';
}
export function passwordGuidance(password: string) {
  const length = Array.from(password).length;
  // Match API's Unicode character minimum and UTF-8 bound. This is guidance,
  // never an entropy estimate, breach check, or claim that a password is secure.
  const bytes = Array.from(password).reduce((sum, character) => { const code = character.codePointAt(0)!; return sum + (code <= 0x7f ? 1 : code <= 0x7ff ? 2 : code <= 0xffff ? 3 : 4); }, 0);
  if (!password) return { level: 0, valid: false, text: 'Use at least 8 characters. A long, unique passphrase is easier to remember.' };
  if (!password.trim()) return { level: 0, valid: false, text: 'A password cannot contain only spaces.' };
  if (bytes > 4096) return { level: 0, valid: false, text: 'Use no more than 4,096 UTF-8 bytes.' };
  if (length < 8) return { level: 1, valid: false, text: 'Use at least 8 characters. Spaces and Slovak characters are welcome.' };
  if (length < 15) return { level: 2, valid: true, text: 'Minimum length met. Try a longer, unique passphrase; avoid reused or common passwords.' };
  return { level: 3, valid: true, text: 'Longer passphrase. Keep it unique; length alone cannot guarantee strength.' };
}
export function formatCount(value: number, locale?: string) {
  return Math.max(0, Math.trunc(Number.isFinite(value) ? value : 0)).toLocaleString(locale);
}
/** Synchronous lock prevents duplicate native events before React can render. */
export function createActionGate() {
  const active = new Set<string>();
  return {
    enter(key: string) { if (active.has(key)) return false; active.add(key); return true; },
    leave(key: string) { active.delete(key); },
    has(key: string) { return active.has(key); },
  };
}
export function applySaved<T extends { id: string }>(items: T[] = [], event: T, saved: boolean): T[] {
  const others = items.filter(item => item.id !== event.id);
  return saved ? [...others, items.find(item => item.id === event.id) ?? event] : others;
}
export function notificationRoute(kind: string, target: string | null): string | null {
  if (kind === 'moderation') return '/activity';
  if (kind === 'privacy_request') return '/privacy';
  if (kind === 'organizer') return '/(tabs)/explore?domain=organizers';
  if (!target || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(target)) return null;
  if (kind === 'message') return `/messages/${target}`;
  if (kind === 'group') return `/group/${target}`;
  return null;
}
