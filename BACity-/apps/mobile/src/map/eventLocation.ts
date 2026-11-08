import type { EventOut } from '../types/event';
export function eventCoordinates(event: Pick<EventOut,'latitude'|'longitude'|'address'|'venue'>): [number,number] | null {
  const place = `${event.venue?.name || ''} ${event.address || ''}`;
  if (/various venues|multiple venues|rôzne miesta|viacero miest/i.test(place)) return null;
  const lat = event.latitude ?? event.venue?.latitude;
  const lng = event.longitude ?? event.venue?.longitude;
  if (typeof lat !== 'number' || typeof lng !== 'number' || !Number.isFinite(lat) || !Number.isFinite(lng) || lat < 48 || lat > 48.35 || lng < 16.9 || lng > 17.35) return null;
  // The application's initial camera is never evidence of an event location.
  if (lat === 48.1486 && lng === 17.1077) return null;
  return [lng,lat];
}
