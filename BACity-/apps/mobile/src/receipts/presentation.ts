import type { EveningPlanAlternative } from '../api/eveningPlans';
import type { WeekendPlanAlternative } from '../api/weekendPlans';
import type { EventOut } from '../types/event';

export type PrintedStop = { key: string; event: EventOut; reason?: string };
export type PrintedDay = { key: string; label: string; stops: PrintedStop[] };
export type PrintedPlan = { title: string; explanation: string; days: PrintedDay[]; count: number };
const ZONE = 'Europe/Bratislava';

function validDate(value: string | null | undefined) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date : null;
}

export function receiptDate(value: string, includeWeekday = true) {
  const date = validDate(/^\d{4}-\d{2}-\d{2}$/.test(value) ? value + 'T12:00:00Z' : value);
  return date ? new Intl.DateTimeFormat('en-GB', { timeZone: ZONE, ...(includeWeekday ? { weekday: 'long' as const } : {}), day: 'numeric', month: 'short', year: 'numeric' }).format(date) : 'Date unconfirmed';
}

export function receiptTime(event: Pick<EventOut, 'start_time' | 'end_time' | 'start_precision'>) {
  if (event.start_precision === 'date') return 'Time unconfirmed';
  const start = validDate(event.start_time);
  if (!start) return 'Time unconfirmed';
  const clock = (date: Date) => new Intl.DateTimeFormat('en-GB', { timeZone: ZONE, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(date);
  const end = validDate(event.end_time);
  return clock(start) + (end && end >= start ? ' – ' + clock(end) : ' · end unconfirmed');
}

function stops(items: { event: EventOut; reasons: string[] }[]): PrintedStop[] {
  // Preserve the engine's order and occurrences, including repeated canonical IDs.
  return items.map((item, index) => ({ key: `${item.event.id}:${item.event.start_time}:${index}`, event: item.event, reason: item.reasons[0] }));
}
export function eveningReceipt(plan: EveningPlanAlternative): PrintedPlan {
  const days: PrintedDay[] = [];
  for (const stop of stops(plan.items)) {
    const label = receiptDate(stop.event.start_time);
    const previous = days[days.length - 1];
    if (previous?.label === label) previous.stops.push(stop);
    else days.push({ key: `${label}:${days.length}`, label, stops: [stop] });
  }
  return { title: 'Build My Evening', explanation: plan.explanation, days, count: plan.items.length };
}
export function weekendReceipt(plan: WeekendPlanAlternative): PrintedPlan {
  const days = plan.days.map((day, index) => ({ key: `${day.date}:${index}`, label: `${day.day} · ${receiptDate(day.date, false)}`, stops: stops(day.items) }));
  return { title: 'Weekend Generator', explanation: plan.explanation, days, count: days.reduce((sum, day) => sum + day.stops.length, 0) };
}
export function receiptVenue(event: EventOut) { return event.venue?.name || event.address || 'Location unconfirmed'; }

export function stopNotice(event: EventOut) {
  const messages: string[] = [];
  if (['cancelled', 'removed', 'postponed', 'expired', 'stale'].includes(event.status)) messages.push(event.status);
  if (event.end_date) messages.push(`Multi-day · through ${receiptDate(event.end_date)}`);
  if (event.identity_kind === 'recurring') messages.push(event.recurrence_label || 'Recurring event · selected occurrence');
  return messages.join(' · ');
}
export function sharePlan(plan: PrintedPlan) {
  return ['BACity+', plan.title, plan.explanation, ...plan.days.flatMap(day => [
    '', day.label, ...day.stops.flatMap(({ event, reason }) => [
      `${receiptTime(event)} | ${event.title}`, receiptVenue(event), ...(stopNotice(event) ? [stopNotice(event)] : []), ...(reason ? [reason] : []),
    ]), ...(day.stops.length ? [] : ['No events safely fit this day.']),
  ]), '', `${plan.count} stops · Europe/Bratislava`, 'A suggested plan. Admission and reservations are not included.'].join('\n');
}

/** UI-thread feed function: short advances alternate with quiet mechanical pauses.
 * Original native implementation; no third-party source, textures or keyframes. */
export function feedPosition(progress: number, stepped: boolean) {
  'worklet';
  const clamped = Math.max(0, Math.min(1, progress));
  if (!stepped || clamped === 1) return clamped;
  const phase = clamped * 11;
  const step = Math.floor(phase);
  const advance = Math.min(1, (phase - step) / .72);
  return (step + advance * advance * (3 - 2 * advance)) / 11;
}
export function printDuration(height: number) { return Math.min(1850, Math.max(1250, 1150 + Math.max(0, height) * .7)); }
export function receiptIsComplete(pending: boolean, resultKey: string | null, completedKey: string | null) {
  return !pending && resultKey !== null && resultKey === completedKey;
}

/** A subscription entitlement or a Checkout redirect is not a paid receipt. */
export type VerifiedPayment = {
  receipt_id: string; payment_status: 'paid'; verification_source: 'provider_confirmed';
  product: string; paid_at: string; amount_minor: number; currency: string; currency_exponent: number;
  transaction_reference: string; merchant_name?: string;
};
export function verifiedPayment(value: unknown): VerifiedPayment | null {
  if (!value || typeof value !== 'object') return null;
  const data = value as Record<string, unknown>;
  if (data.payment_status !== 'paid' || data.verification_source !== 'provider_confirmed') return null;
  for (const name of ['receipt_id', 'product', 'transaction_reference']) if (typeof data[name] !== 'string' || !(data[name] as string).trim() || (data[name] as string).length > 500) return null;
  if (typeof data.paid_at !== 'string' || !/([zZ]|[+-]\d\d:\d\d)$/.test(data.paid_at) || !validDate(data.paid_at)) return null;
  if (!Number.isSafeInteger(data.amount_minor) || (data.amount_minor as number) < 0 || typeof data.currency !== 'string' || !/^[A-Z]{3}$/.test(data.currency)) return null;
  if (!Number.isInteger(data.currency_exponent) || (data.currency_exponent as number) < 0 || (data.currency_exponent as number) > 3) return null;
  return { receipt_id: data.receipt_id as string, product: data.product as string, transaction_reference: data.transaction_reference as string,
    paid_at: data.paid_at, payment_status: 'paid', verification_source: 'provider_confirmed', amount_minor: data.amount_minor as number,
    currency: data.currency, currency_exponent: data.currency_exponent as number,
    ...(typeof data.merchant_name === 'string' && data.merchant_name.trim() ? { merchant_name: data.merchant_name.slice(0, 300) } : {}) };
}
