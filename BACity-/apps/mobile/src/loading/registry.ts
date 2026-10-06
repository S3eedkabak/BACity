export type LoadingContext = 'startup' | 'event-details' | 'saved' | 'explore' | 'search' | 'map';
// Enumerated with @rive-app/canvas 2.44.0 against the supplied, unchanged file.
// 800x1000 artboard; loop=1; durations are frames at 60fps (2s/4s/2s).
// State Machine 1 has one NUMBER input "level"; no booleans/triggers.
// *_press timelines are one-shot button treatments, NOT loading cycles.
export const walkAsset = {
  artboard: 'New Artboard',
  cycles: ['Beginner', 'Intermediate', 'Expert'],
  stateMachines: [{ name: 'State Machine 1', inputs: [{ name: 'level', type: 'number' }] }],
} as const;
export const loadingRegistry = {
  startup: { animation: 'Beginner', copy: 'Getting the city ready…' },
  'event-details': { animation: 'Intermediate', copy: 'Getting the details…' },
  saved: { animation: 'Expert', copy: 'Getting your plans…' },
  explore: { animation: 'Intermediate', copy: 'Finding something good…' },
  search: { animation: 'Beginner', copy: 'Looking around…' },
  map: { animation: 'Expert', copy: 'Putting the city on the map…' },
} as const satisfies Record<LoadingContext, { animation: typeof walkAsset.cycles[number]; copy: string }>;
