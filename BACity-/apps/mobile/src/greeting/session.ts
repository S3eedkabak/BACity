export type Greeting = { owner: string; kind: 'new' | 'returning'; deadline: number };
// Process-local, deliberately NOT AsyncStorage. Retains the same claim through
// StrictMode/root remounts; account changes never replay an already claimed entry.
export function createSessionGreeting() {
  let phase: 'restoring' | 'greeting' | 'complete' = 'restoring';
  let active: Greeting | null = null;
  return {
    claim(owner: string | null, restoring: boolean, kind: Greeting['kind'], now: number): Greeting | null {
      if (!owner) {
        if (phase === 'greeting') { phase = 'complete'; active = null; }
        return null;
      }
      if (restoring) return null;
      if (phase === 'restoring') {
        active = { owner, kind, deadline: now + 2200 };
        phase = 'greeting';
      }
      if (active && (active.owner !== owner || now >= active.deadline)) {
        phase = 'complete'; active = null;
      }
      return active;
    },
    finish(owner: string) {
      if (active?.owner === owner) { phase = 'complete'; active = null; }
    },
  };
}
export const sessionGreeting = createSessionGreeting();
