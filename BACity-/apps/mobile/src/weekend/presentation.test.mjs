import assert from "node:assert/strict";
import test from "node:test";
import { defaultWeekendStart, isChronologicalWeekendPlan, resolveWeekendView, validateWeekendStart, weekendEventRoute, weekendPlanNotice, weekendPlanRoute } from "./presentation.ts";

test("entitlement loading, failure, and paywall never reveal Weekend Generator", () => {
  assert.equal(resolveWeekendView("loading", false, false, false, 0), "guarding");
  assert.equal(resolveWeekendView("error", false, false, false, 0), "guarding");
  assert.equal(resolveWeekendView("paywall", false, false, false, 0), "guarding");
  assert.equal(resolveWeekendView("allow", false, false, false, 0), "parameters");
});

test("defaults choose the current or next Bratislava weekend", () => {
  assert.equal(defaultWeekendStart(new Date("2030-06-14T10:00:00Z")), "2030-06-15");
  assert.equal(defaultWeekendStart(new Date("2030-06-15T10:00:00Z")), "2030-06-15");
  assert.equal(defaultWeekendStart(new Date("2030-06-16T10:00:00Z")), "2030-06-15");
});

test("weekend validation rejects malformed, invalid, non-Saturday, and past values", () => {
  const now = new Date("2030-06-14T10:00:00Z");
  assert.equal(validateWeekendStart("2030-06-15", now), null);
  assert.match(validateWeekendStart("bad", now), /YYYY/);
  assert.match(validateWeekendStart("2030-02-30", now), /valid/);
  assert.match(validateWeekendStart("2030-06-16", now), /Saturday/);
  assert.match(validateWeekendStart("2030-06-08", now), /ended/);
});

test("generation exposes loading, error, empty, limited, and successful states", () => {
  assert.equal(resolveWeekendView("allow", true, true, false, 0), "loading");
  assert.equal(resolveWeekendView("allow", true, false, true, 0), "error");
  assert.equal(resolveWeekendView("allow", true, false, false, 0), "empty");
  assert.equal(resolveWeekendView("allow", true, false, false, 2), "results");
  const limited = { limited: true, days: [{ day: "Saturday", items: [{}] }, { day: "Sunday", items: [] }] };
  assert.match(weekendPlanNotice(limited), /Sunday/);
});

test("plans preserve day-local chronology and normal event navigation", () => {
  const event = (id, start) => ({ event: { id, start_time: start } });
  const plan = { days: [
    { items: [event("a", "2030-06-15T09:00:00Z"), event("b", "2030-06-15T14:00:00Z")] },
    { items: [event("c", "2030-06-16T10:00:00Z")] },
  ] };
  assert.equal(isChronologicalWeekendPlan(plan), true);
  assert.equal(weekendPlanRoute(), "/weekend-plan");
  assert.equal(weekendEventRoute("event-1"), "/event/event-1");
});
