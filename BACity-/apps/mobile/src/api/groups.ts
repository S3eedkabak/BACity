import { apiRequest } from "./client";
import type { EventCategory, EventOut } from "../types/event";

export type GroupStatus = "open" | "ready" | "voting" | "completed" | "expired" | "cancelled";
export type VoteValue = -1 | 0 | 1;

export interface GroupSummary {
  id: string;
  name: string;
  status: GroupStatus;
  target_date: string;
  starts_at: string;
  ends_at: string;
  participant_count: number;
  max_participants: number;
  role: "host" | "participant";
}

export interface GroupParticipant {
  id: string;
  display_name: string;
  avatar_url: string | null;
  is_host: boolean;
  ready: boolean;
}

export interface GroupCandidate {
  id: string;
  event: EventOut;
  explanations: string[];
  my_vote: VoteValue | null;
  aggregate: { likes: number; neutral: number; dislikes: number; score: number } | null;
}

export interface GroupRound {
  id: string;
  number: number;
  status: "voting" | "completed";
  voted_participants: number;
  participant_count: number;
  candidates: GroupCandidate[];
}

export interface GroupDetail extends GroupSummary {
  categories: EventCategory[];
  expires_at: string;
  participants: GroupParticipant[];
  round: GroupRound | null;
}

export interface GroupCreateRequest {
  name: string;
  target_date: string;
  start_time: string;
  end_time: string;
  categories: EventCategory[];
  max_participants: number;
}

export const groupsApi = {
  list: () => apiRequest<GroupSummary[]>("/groups", { auth: true }),
  get: (id: string) => apiRequest<GroupDetail>(`/groups/${id}`, { auth: true }),
  create: (payload: GroupCreateRequest) => apiRequest<{ group: GroupDetail; join_code: string; join_code_expires_at: string }>("/groups", { method: "POST", auth: true, body: payload }),
  join: (code: string) => apiRequest<GroupDetail>("/groups/join", { method: "POST", auth: true, body: { code } }),
  preferences: (id: string, liked: EventCategory[], disliked: EventCategory[]) => apiRequest<GroupDetail>(`/groups/${id}/preferences`, { method: "PATCH", auth: true, body: { liked_categories: liked, disliked_categories: disliked, ready: true } }),
  generate: (id: string, coordinates: { latitude: number; longitude: number } | null) => apiRequest<GroupDetail>(`/groups/${id}/matches`, { method: "POST", auth: true, body: coordinates ?? {} }),
  vote: (id: string, roundId: string, candidateId: string, value: VoteValue) => apiRequest<GroupDetail>(`/groups/${id}/rounds/${roundId}/vote`, { method: "PATCH", auth: true, body: { candidate_id: candidateId, value } }),
  reveal: (id: string, roundId: string) => apiRequest<GroupDetail>(`/groups/${id}/rounds/${roundId}/reveal`, { method: "POST", auth: true }),
  invite: (id: string) => apiRequest<{ join_code: string; expires_at: string }>(`/groups/${id}/invite`, { method: "POST", auth: true }),
  cancel: (id: string) => apiRequest<GroupDetail>(`/groups/${id}/cancel`, { method: "POST", auth: true }),
  leave: (id: string) => apiRequest<{ left: boolean }>(`/groups/${id}/members/me`, { method: "DELETE", auth: true }),
};
