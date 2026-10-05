import { apiRequest } from './client';

export const privacyKinds = ['ACCESS', 'RECTIFICATION', 'ERASURE', 'RESTRICTION', 'PORTABILITY', 'OBJECTION', 'OTHER_PRIVACY_REQUEST'] as const;
export type PrivacyKind = typeof privacyKinds[number];
export type PrivacyRequest = {
  id: string; kind: PrivacyKind; status: string; due_at: string; created_at: string;
  overdue: boolean; extended: boolean; details?: string; response?: string;
};
export type PrivacyInformation = {
  controller_legal_name: string | null; business_address: string | null;
  support_contact_email: string | null; legal_contact_email: string | null;
  privacy_contact_email: string | null; privacy_notice_url: string | null; terms_url: string | null;
  privacy_notice_version: string | null; terms_version: string | null; documents_ready: boolean;
  message_encryption: string; location: string; recommendations: string;
};
export const privacyApi = {
  information: () => apiRequest<PrivacyInformation>('/privacy/information'),
  requests: (offset = 0) => apiRequest<PrivacyRequest[]>(`/privacy/requests?offset=${offset}&limit=20`, { auth: true }),
  submit: (kind: PrivacyKind, details: string) => apiRequest<PrivacyRequest>('/privacy/requests', { method: 'POST', auth: true, body: { kind, details } }),
};
