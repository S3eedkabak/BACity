import type { MapFilters } from './area';
const day = (value: string) => new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric', timeZone: 'Europe/Bratislava' });
/** The same labels drive the visible button and its spoken filter state. */
export function appliedFilterLabels(value: MapFilters): string[] {
  return [
    value.category,
    value.free_only ? 'Free' : null,
    value.status === 'fresh' ? 'Fresh listings' : value.status === 'stale' ? 'Older listings' : null,
    value.starts_after ? day(value.starts_after) + (value.starts_before ? ' – ' + day(value.starts_before) : ' onward') : value.starts_before ? 'Until ' + day(value.starts_before) : null,
    value.q?.trim() ? '“' + value.q.trim() + '”' : null,
  ].filter((label): label is string => !!label);
}
export function filterSummary(value: MapFilters) {
  return appliedFilterLabels(value).join(' · ') || 'Any time · All interests';
}
