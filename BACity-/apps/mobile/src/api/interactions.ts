import { apiRequest } from './client';
export type Review = { id: string; user_id: string; body: string; dimensions: Record<string, number>; attendance_verified: boolean; helpful: number };
export type ReviewSummary = { count: number; dimensions: Record<string, { average: number; count: number }> };
export const getReviews = (kind: 'event' | 'place', id: string) => apiRequest<Review[]>(`/community/reviews/${kind}/${id}`, { auth: true });
export const getReviewSummary = (kind: 'event' | 'place', id: string) => apiRequest<ReviewSummary>(`/community/review-summary/${kind}/${id}`, { auth: true });
export const publishReview = (kind: 'event' | 'place', id: string, body: string, dimensions: Record<string, number>) => apiRequest<Review>('/community/reviews', { method: 'POST', auth: true, body: { target_type: kind, target_id: id, body, dimensions } });
export const getNotificationSummary = () => apiRequest<{ unread: number; messages: number }>('/community/notification-summary', { auth: true });
