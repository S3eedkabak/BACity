import type { EveningPlanAlternative } from "../api/eveningPlans";
import type { PlusGateDecision } from "../plus/policy";

export type EveningViewState = "guarding" | "parameters" | "loading" | "error" | "empty" | "results";

const pad = (value: number) => String(value).padStart(2, "0");

export function defaultEveningParameters(now = new Date()) {
  const day = new Date(now);
  if (day.getHours() >= 22) day.setDate(day.getDate() + 1);
  return {
    date: `${day.getFullYear()}-${pad(day.getMonth() + 1)}-${pad(day.getDate())}`,
    startTime: "18:00",
    endTime: "00:00",
  };
}

export function validateEveningParameters(date: string, startTime: string, endTime: string, now = new Date()) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !/^\d{2}:\d{2}$/.test(startTime) || !/^\d{2}:\d{2}$/.test(endTime)) {
    return "Use YYYY-MM-DD and HH:MM.";
  }
  const start = new Date(`${date}T${startTime}:00`);
  const end = new Date(`${date}T${endTime}:00`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return "Enter a valid date and time.";
  if (startTime === endTime) return "Start and end time must differ.";
  if (end <= start) end.setDate(end.getDate() + 1);
  if (end.getTime() - start.getTime() > 10 * 60 * 60 * 1000) return "Evening plans can cover at most 10 hours.";
  if (end <= now) return "Choose an evening that has not ended.";
  return null;
}

export function resolveEveningView(
  gate: PlusGateDecision,
  submitted: boolean,
  pending: boolean,
  failed: boolean,
  planCount: number,
): EveningViewState {
  if (gate !== "allow") return "guarding";
  if (pending) return "loading";
  if (failed) return "error";
  if (!submitted) return "parameters";
  return planCount === 0 ? "empty" : "results";
}

export function isChronologicalPlan(plan: EveningPlanAlternative) {
  return plan.items.every((item, index) => index === 0
    || new Date(plan.items[index - 1].event.start_time) <= new Date(item.event.start_time));
}

export function eveningPlanNotice(limited: boolean) {
  return limited ? "Limited result: only one event safely fits." : null;
}

export function eveningPlanRoute() {
  return "/evening-plan" as const;
}

export function eveningEventRoute(eventId: string) {
  return `/event/${eventId}` as const;
}
