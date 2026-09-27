export function selectFeaturedEvent<T>(events: T[]): T | undefined {
  return events[0];
}

export function excludeFeaturedEvent<T extends { event: { id: string } }>(items: T[], featuredId?: string): T[] {
  return featuredId ? items.filter((item) => item.event.id !== featuredId) : items;
}
