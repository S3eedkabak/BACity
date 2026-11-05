export function selectFeaturedEvent<T extends { image_url?: string | null }>(events: T[]): T | undefined {
  return events.find(event => !!event.image_url?.trim()) ?? events[0];
}

export function excludeFeaturedEvent<T extends { event: { id: string } }>(items: T[], featuredId?: string): T[] {
  return featuredId ? items.filter((item) => item.event.id !== featuredId) : items;
}
