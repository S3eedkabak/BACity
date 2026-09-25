import { useState } from 'react';
import { Text, Switch } from 'react-native';
import { useLocalSearchParams, router } from 'expo-router';
import { apiRequest } from '../src/api/client';
import { useAuthStore } from '../src/store/authStore';
import { Page, Card, Field, Button, Notice, ui } from '../src/components/CommunityUI';

export default function Account() {
  const { action, token } = useLocalSearchParams<{ action?: string; token?: string }>();
  const { user, refreshUser, logout } = useAuthStore();
  const [name, setName] = useState(user?.display_name ?? '');
  const [bio, setBio] = useState(user?.bio ?? '');
  const [neighborhood, setNeighborhood] = useState(user?.neighborhood ?? '');
  const [interests, setInterests] = useState(user?.interests.join(', ') ?? '');
  const [isPublic, setPublic] = useState(user?.public_profile ?? true);
  const [messages, setMessages] = useState(user?.allow_general_messages ?? false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  async function run(fn: () => Promise<unknown>, success: string) {
    setBusy(true); setNotice('');
    try { await fn(); setNotice(success); } catch (e: any) { setNotice(e.message); } finally { setBusy(false); }
  }
  return <Page title="Your account">
    <Notice text={notice} />
    {token && action === 'verify' && <Card><Text style={ui.text}>Confirm your email address to contribute to BACity.</Text><Button busy={busy} title="Verify email" onPress={() => run(async () => { await apiRequest('/auth/verify-email', { method: 'POST', body: { token } }); await refreshUser(); }, 'Email verified. You can now contribute.')} /></Card>}
    {token && action === 'reset' && <Card><Field label="New password (8–72 characters)" secure value={password} onChange={setPassword} /><Button busy={busy} title="Reset password" onPress={() => run(() => apiRequest('/auth/reset-password', { method: 'POST', body: { token, password } }), 'Password changed. Sign in with your new password.')} /></Card>}
    {!user ? <Card><Field label="Email address" value={email} onChange={setEmail} /><Button busy={busy} title="Send password reset email" onPress={() => run(() => apiRequest('/auth/request-reset', { method: 'POST', body: { email } }), 'If the account exists, a reset email has been queued.')} /><Button title="Sign in" onPress={() => router.push('/(tabs)/profile')} /></Card> : <>
      {!user.email_verified && <Card><Text style={ui.text}>Verify your email before submitting, following, or messaging.</Text><Button title="Resend verification email" busy={busy} onPress={() => run(() => apiRequest('/auth/request-verification', { method: 'POST', auth: true }), 'Verification email queued.')} /><Button title="I verified my email — refresh" busy={busy} onPress={() => run(refreshUser, 'Account refreshed.')} /></Card>}
      <Card><Field label="Display name" value={name} onChange={setName} /><Field label="Bio" value={bio} onChange={setBio} multiline /><Field label="Neighborhood" value={neighborhood} onChange={setNeighborhood} /><Field label="Interests (comma separated)" value={interests} onChange={setInterests} /><Text style={ui.text}>Public profile</Text><Switch accessibilityLabel="Public profile" value={isPublic} onValueChange={setPublic} /><Text style={ui.text}>Allow messages from people you do not follow</Text><Switch accessibilityLabel="Allow general messages" value={messages} onValueChange={setMessages} /><Button title="Save preferences" busy={busy} onPress={() => run(async () => { await apiRequest('/community/profile', { method: 'PATCH', auth: true, body: { display_name: name || null, bio, neighborhood, interests: interests.split(',').map(i => i.trim()).filter(Boolean), public_profile: isPublic, allow_general_messages: messages } }); await refreshUser(); }, 'Preferences saved.')} /></Card>
      <Card><Text style={ui.heading}>Delete account</Text><Text style={ui.text}>This disables your account, removes private messages and profile details, and retains published contributions under a deleted-account identity.</Text>{confirmDelete ? <><Button title="Delete my account permanently" busy={busy} onPress={() => run(async () => { await apiRequest('/community/account', { method: 'DELETE', auth: true, body: { reason: 'User requested account deletion' } }); await logout(); }, 'Account deleted.')} /><Button title="Keep account" onPress={() => setConfirmDelete(false)} /></> : <Button title="Review account deletion" onPress={() => setConfirmDelete(true)} />}</Card>
    </>}
  </Page>;
}
