import type { WeekendPlanAlternative } from "../api/weekendPlans";
import type { PlusGateDecision } from "../plus/policy";

export type WeekendViewState = "guarding" | "parameters" | "loading" | "error" | "empty" | "results";

const pad = (value: number) => String(value).padStart(2, "0");

function bratislavaCalendar(now: Date) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Bratislava", year: "numeric", month: "2-digit", day: "2-digit", weekday: "short",
  }).formatToParts(now);
  const read = (type: Intl.DateTimeFormatPartTypes) => parts.find(part => part.type === type)?.value ?? "";
  return { year: Number(read("year")), month: Number(read("month")), day: Number(read("day")), weekday: read("weekday") };
}

export function defaultWeekendStart(now = new Date()) {
  const local = bratislavaCalendar(now);
  const weekday = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].indexOf(local.weekday);
  const offset = weekday === 0 ? -1 : (6 - weekday + 7) % 7;
  const result = new Date(Date.UTC(local.year, local.month - 1, local.day + offset));
  return `${result.getUTCFullYear()}-${pad(result.getUTCMonth() + 1)}-${pad(result.getUTCDate())}`;
}

export function validateWeekendStart(value: string, now = new Date()) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return "Use YYYY-MM-DD for the weekend Saturday.";
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)!;
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  if (date.getUTCFullYear() !== Number(match[1]) || date.getUTCMonth() !== Number(match[2]) - 1 || date.getUTCDate() !== Number(match[3])) return "Enter a valid date.";
  if (date.getUTCDay() !== 6) return "Choose the Saturday that starts the weekend.";
  const current = defaultWeekendStart(now);
  if (value < current) return "Choose a weekend that has not ended.";
  return null;
}

export function resolveWeekendView(
  gate: PlusGateDecision,
  submitted: boolean,
  pending: boolean,
  failed: boolean,
  planCount: number,
): WeekendViewState {
  if (gate !== "allow") return "guarding";
  if (pending) return "loading";
  if (failed) return "error";
  if (!submitted) return "parameters";
  return planCount === 0 ? "empty" : "results";
}

export function weekendPlanRoute() {
  return "/weekend-plan" as const;
}

export function weekendEventRoute(eventId: string) {
  return `/event/${eventId}` as const;
}

export function isChronologicalWeekendPlan(plan: WeekendPlanAlternative) {
  return plan.days.every(day => day.items.every((item, index) => index === 0
    || new Date(day.items[index - 1].event.start_time) <= new Date(item.event.start_time)));
}

export function weekendPlanNotice(plan: WeekendPlanAlternative) {
  if (!plan.limited) return null;
  const emptyDays = plan.days.filter(day => day.items.length === 0).map(day => day.day);
  if (emptyDays.length) return `Limited result: no safe ${emptyDays.join(" or ")} events fit.`;
  return "Limited result: only a small number of events safely fit.";
}
