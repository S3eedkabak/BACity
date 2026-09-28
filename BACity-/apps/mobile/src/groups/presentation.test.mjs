import assert from "node:assert/strict";
import test from "node:test";
import { aggregatesArePrivate, applyLocalVote, groupEventRoute, groupRoute, groupStateLabel, hostPremiumAction, mayParticipate, resolveGroupsView } from "./presentation.ts";

test("only initiating host actions use the Plus gate", () => {
  assert.equal(hostPremiumAction("allow", true), "allow");
  assert.equal(hostPremiumAction("paywall", true), "paywall");
  assert.equal(hostPremiumAction("error", true), "paywall");
  assert.equal(hostPremiumAction("loading", true), "wait");
  assert.equal(hostPremiumAction("allow", false), "forbidden");
  assert.equal(mayParticipate(true, true), true);
  assert.equal(mayParticipate(true, false), false);
});

test("group list exposes signed-out, loading, error, empty and result states", () => {
  assert.equal(resolveGroupsView(false, false, false, 0), "signed_out");
  assert.equal(resolveGroupsView(true, true, false, 0), "loading");
  assert.equal(resolveGroupsView(true, false, true, 0), "error");
  assert.equal(resolveGroupsView(true, false, false, 0), "empty");
  assert.equal(resolveGroupsView(true, false, false, 2), "list");
});

test("Free participants can reach group and event routes without a paywall decision", () => {
  assert.equal(groupRoute("g1"), "/group/g1");
  assert.equal(groupEventRoute("e1"), "/event/e1");
  assert.equal(groupStateLabel("voting"), "Voting open");
  assert.equal(groupStateLabel("expired"), "Expired");
});

test("vote changes replace the participant's current local choice", () => {
  const first = applyLocalVote({}, "c1", 1);
  assert.deepEqual(applyLocalVote(first, "c1", -1), { c1: -1 });
});

test("active voting never exposes aggregate choices", () => {
  const group = { round: { status: "voting", candidates: [{ aggregate: null }, { aggregate: null }] } };
  assert.equal(aggregatesArePrivate(group), true);
  assert.equal(aggregatesArePrivate({ round: { status: "voting", candidates: [{ aggregate: { likes: 1 } }] } }), false);
});
