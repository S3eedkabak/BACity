import type { GroupDetail, GroupStatus, VoteValue } from "../api/groups";
import type { PlusGateDecision } from "../plus/policy";

export type GroupsView = "signed_out" | "loading" | "error" | "empty" | "list";

export function resolveGroupsView(authenticated: boolean, pending: boolean, failed: boolean, count: number): GroupsView {
  if (!authenticated) return "signed_out";
  if (pending) return "loading";
  if (failed) return "error";
  return count ? "list" : "empty";
}

export function mayParticipate(authenticated: boolean, membership: boolean) {
  return authenticated && membership;
}

export function hostPremiumAction(gate: PlusGateDecision, isHost: boolean) {
  if (!isHost) return "forbidden" as const;
  if (gate === "allow") return "allow" as const;
  if (gate === "loading") return "wait" as const;
  return "paywall" as const;
}

export function groupStateLabel(status: GroupStatus) {
  return ({
    open: "Waiting for preferences", ready: "Ready to match", voting: "Voting open",
    completed: "Results ready", expired: "Expired", cancelled: "Cancelled",
  } as const)[status];
}

export function groupRoute(id: string) {
  return `/group/${id}` as const;
}

export function groupEventRoute(eventId: string) {
  return `/event/${eventId}` as const;
}

export function applyLocalVote(current: Record<string, VoteValue>, candidateId: string, value: VoteValue) {
  return { ...current, [candidateId]: value };
}

export function aggregatesArePrivate(group: GroupDetail) {
  return group.round?.status === "voting"
    ? group.round.candidates.every(candidate => candidate.aggregate === null)
    : true;
}
