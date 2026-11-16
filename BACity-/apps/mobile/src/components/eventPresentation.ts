export type EventPresentation = "row" | "feature" | "rail" | "editorial";
/** Existing callers retain their contract while new views choose an actual layout. */
export const eventPresentations = {
  home: "editorial",
  hero: "feature",
  horizontal: "rail",
  feed: "row",
  compact: "row",
  map: "row",
  saved: "row",
  planner: "row",
  premium: "row",
  organizer: "row",
} as const satisfies Record<string, EventPresentation>;
export type EventCardVariant = keyof typeof eventPresentations;
