import { apiRequest, ApiError } from "./client";

export type PublicProfile = {
  id: string; display_name: string | null; avatar_url: string | null; bio: string | null;
  city: string; neighborhood: string | null; interests: string[]; role: string;
  identity_verified: boolean; reputation: number; reputation_level: string;
  contributions_count: number; reviews_count: number; followers: number; following: number;
  is_following?: boolean; follow_id?: string | null;
};
export type Message = { id: string; sender_id: string; recipient_id: string; body: string; created_at: string; read_at: string | null };
export type Notification = { id: string; kind: string; body: string; target_id: string | null; created_at: string; read_at: string | null };
export type FollowRecord = { id: string; target_type: string; target_id: string; target_label: string; target_subtitle: string; created_at: string };

export const getProfile = (id: string) => apiRequest<PublicProfile>(`/community/profiles/${id}`, { auth: true });
// An unavailable profile must not destroy an authorized recipient's history.
// Never infer why a profile is unavailable or reuse its cached identity.
export async function getConversationProfile(id: string) {
  try { return await getProfile(id); }
  catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return { display_name: 'Unavailable member', avatar_url: null, unavailable: true };
    }
    throw error;
  }
}
export const getProfileHistory = (id: string, type: "contributions" | "reviews" | "followers" | "following", offset = 0, limit = 20) => apiRequest<any[]>(`/community/profiles/${id}/${type}`, { auth: true, params: { offset, limit } });
export const getNotifications = () => apiRequest<Notification[]>("/community/notifications", { auth: true });
export const markNotificationRead = (id: string) => apiRequest(`/community/notifications/${id}/read`, { method: "POST", auth: true });
export const getConversation = (id: string, offset = 0) => apiRequest<Message[]>(`/community/messages/${id}`, { auth: true, params: { offset } });
export const sendMessage = (id: string, body: string) => apiRequest<Message>(`/community/messages/${id}`, { method: "POST", auth: true, body: { body } });
export const getFollows = (offset = 0, limit = 50) => apiRequest<FollowRecord[]>("/community/follows", { auth: true, params: { offset, limit } });
export const follow = (target_type: string, target_id: string) => apiRequest("/community/follows", { method: "POST", auth: true, body: { target_type, target_id } });
export const unfollow = (id: string) => apiRequest(`/community/follows/${id}`, { method: "DELETE", auth: true });
