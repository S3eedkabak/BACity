import type { EventOut } from '../types/event';
const zone = 'Europe/Bratislava';
type Schedule = Pick<EventOut, 'start_time'|'end_time'|'end_date'|'identity_kind'|'next_occurrence_start'|'recurrence_label'|'start_precision'>;
const dayKey = (date: Date) => new Intl.DateTimeFormat('en-CA', {timeZone:zone, year:'numeric', month:'2-digit', day:'2-digit'}).format(date);
const day = (date: Date) => date.toLocaleDateString(undefined, {timeZone:zone, day:'numeric', month:'short', year:'numeric'});
export function availabilityLabel(event: Schedule, now = new Date()) {
  const start = new Date(event.next_occurrence_start ?? event.start_time);
  if (!Number.isFinite(start.getTime())) return 'Schedule unavailable';
  const clock = start.toLocaleTimeString(undefined, {timeZone:zone, hour:'2-digit', minute:'2-digit'});
  if (event.identity_kind === 'recurring') {
    return `Recurring · ${event.recurrence_label || 'Selected dates'}\nNext availability · ${day(start)}${event.start_precision==='date'?'':` · ${clock}`}`;
  }
  const first = new Date(event.start_time);
  if (!event.end_time && !event.end_date && [2000,2016].includes(first.getUTCFullYear()) && first.getUTCMonth()===0 && first.getUTCDate()===1) return 'Schedule to be confirmed';
  const end = event.end_date ? new Date(`${event.end_date}T12:00:00Z`) : event.end_time ? new Date(event.end_time) : null;
  if (end && Number.isFinite(end.getTime()) && dayKey(first) !== dayKey(end)) {
    const active = first <= now && (event.end_date ? event.end_date >= dayKey(now) : end >= now);
    return `${active ? 'On now · ' : ''}${day(first)} – ${day(end)}`;
  }
  return `${day(start)}${event.start_precision==='date'?'':` · ${clock}`}`;
}
