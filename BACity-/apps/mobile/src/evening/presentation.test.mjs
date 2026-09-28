import assert from "node:assert/strict";
import test from "node:test";
import { defaultEveningParameters, eveningEventRoute, eveningPlanNotice, eveningPlanRoute, isChronologicalPlan, resolveEveningView, validateEveningParameters } from "./presentation.ts";

test("entitlement loading and failure never reveal the planner", () => {
  assert.equal(resolveEveningView("loading", false, false, false, 0), "guarding");
  assert.equal(resolveEveningView("error", false, false, false, 0), "guarding");
  assert.equal(resolveEveningView("paywall", false, false, false, 0), "guarding");
});

test("default parameters provide a six-hour evening and roll late-night setup forward", () => {
  assert.deepEqual(defaultEveningParameters(new Date(2030, 5, 15, 12)), { date: "2030-06-15", startTime: "18:00", endTime: "00:00" });
  assert.equal(defaultEveningParameters(new Date(2030, 5, 15, 23)).date, "2030-06-16");
});

test("parameter validation accepts midnight crossing and rejects malformed, equal, long and past windows", () => {
  const now = new Date(2030, 5, 15, 12);
  assert.equal(validateEveningParameters("2030-06-15", "18:00", "00:00", now), null);
  assert.match(validateEveningParameters("bad", "18:00", "00:00", now), /YYYY/);
  assert.match(validateEveningParameters("2030-06-15", "18:00", "18:00", now), /differ/);
  assert.match(validateEveningParameters("2030-06-15", "10:00", "23:00", now), /10 hours/);
  assert.match(validateEveningParameters("2020-01-01", "18:00", "00:00", now), /ended/);
});

test("generation exposes parameter, loading, error, empty, limited and multiple-plan states", () => {
  assert.equal(resolveEveningView("allow", false, false, false, 0), "parameters");
  assert.equal(resolveEveningView("allow", true, true, false, 0), "loading");
  assert.equal(resolveEveningView("allow", true, false, true, 0), "error");
  assert.equal(resolveEveningView("allow", true, false, false, 0), "empty");
  assert.equal(resolveEveningView("allow", true, false, false, 3), "results");
  assert.equal(eveningPlanNotice(true), "Limited result: only one event safely fits.");
  assert.equal(eveningPlanNotice(false), null);
});

test("plans remain ordered and navigation targets normal event detail", () => {
  const plan = { items: [
    { event: { start_time: "2030-06-15T18:00:00Z" } },
    { event: { start_time: "2030-06-15T20:00:00Z" } },
  ] };
  assert.equal(isChronologicalPlan(plan), true);
  assert.equal(eveningPlanRoute(), "/evening-plan");
  assert.equal(eveningEventRoute("event-1"), "/event/event-1");
});
