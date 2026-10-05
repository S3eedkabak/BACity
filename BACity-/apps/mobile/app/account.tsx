import { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, Share, StyleSheet, Switch, Text, View } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { useLocalSearchParams, router } from 'expo-router';
import { apiRequest } from '../src/api/client';
import { useAuthStore } from '../src/store/authStore';
import { Page, Card, Disclosure, Field, Button, Notice, ui } from '../src/components/CommunityUI';
import { uploadAvatar } from '../src/api/profile';
import { colors } from '../src/theme/colors';
import { fonts } from '../src/theme/fonts';
import { InterestPicker } from '../src/components/InterestPicker';
const INTERESTS = ['Music', 'Culture', 'Nightlife', 'Arts', 'Family', 'Community', 'Sports', 'Food & Drink'] as const;

type ResetLinkState = 'loading' | 'valid' | 'invalid' | 'expired' | 'used' | 'submitting' | 'success' | 'error';

function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [notice, setNotice] = useState('');

  async function requestReset() {
    setBusy(true);
    setNotice('');
    try {
      await apiRequest('/auth/request-reset', { method: 'POST', body: { email: email.trim() } });
      setSubmitted(true);
    } catch (error: any) {
      setNotice(error?.message ?? 'Could not request a reset email. Please try again.');
    } finally {
      setBusy(false);
    }
  }

  if (submitted) {
    return <Card>
      <Text style={ui.heading}>Check your email</Text>
      <Text style={ui.text}>If an account exists for that address, BACity has sent a password-reset link. The link expires after 30 minutes.</Text>
      <Button title="Back to login" onPress={() => router.replace({ pathname: '/auth', params: { mode: 'login' } })} />
      <Pressable accessibilityRole="button" onPress={() => setSubmitted(false)} style={styles.textAction}>
        <Text style={styles.textActionLabel}>Try another email address</Text>
      </Pressable>
    </Card>;
  }

  return <Card>
    <Text style={ui.heading}>Reset your password</Text>
    <Text style={ui.text}>Enter your account email. For privacy, BACity always returns the same confirmation.</Text>
    <Field label="Email address" value={email} onChange={setEmail} />
    <Notice text={notice} />
    <Button busy={busy} title="Send reset link" onPress={requestReset} />
    <Pressable accessibilityRole="button" onPress={() => router.replace({ pathname: '/auth', params: { mode: 'login' } })} style={styles.textAction}>
      <Text style={styles.textActionLabel}>Back to login</Text>
    </Pressable>
  </Card>;
}

function ResetPassword({ token }: { token: string }) {
  const [state, setState] = useState<ResetLinkState>('loading');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [showPasswords, setShowPasswords] = useState(false);
  const [notice, setNotice] = useState('');
  const logout = useAuthStore((current) => current.logout);

  async function inspectToken() {
    if (!token) {
      setState('invalid');
      return;
    }
    setState('loading');
    setNotice('');
    try {
      const result = await apiRequest<{ status: 'valid' | 'invalid' | 'expired' | 'used' }>(
        '/auth/reset-password/status', { method: 'POST', body: { token } }
      );
      setState(result.status);
    } catch (error: any) {
      setNotice(error?.message ?? 'Could not check this reset link.');
      setState('error');
    }
  }

  useEffect(() => { void inspectToken(); }, [token]);

  async function submit() {
    setNotice('');
    if (password.length < 8 || !password.trim()) {
      setNotice('Use at least 8 characters; the password cannot contain only spaces.');
      return;
    }
    if (password !== confirmation) {
      setNotice('The passwords do not match.');
      return;
    }
    setState('submitting');
    try {
      await apiRequest('/auth/reset-password', { method: 'POST', body: { token, password } });
      setPassword('');
      setConfirmation('');
      try { await logout(); } catch { /* The server-side reset still succeeded. */ }
      setState('success');
    } catch (error: any) {
      try {
        const result = await apiRequest<{ status: 'valid' | 'invalid' | 'expired' | 'used' }>(
          '/auth/reset-password/status', { method: 'POST', body: { token } }
        );
        if (result.status !== 'valid') {
          setState(result.status);
          return;
        }
      } catch {
        // Preserve the original reset failure below when status cannot be checked.
      }
      setNotice(error?.message ?? 'Could not reset your password. Please try again.');
      setState('error');
    }
  }

  if (state === 'loading') {
    return <Card><View style={styles.loading}><ActivityIndicator color={colors.primary} /><Text style={ui.text}>Checking your reset link…</Text></View></Card>;
  }
  if (state === 'success') {
    return <Card>
      <Text style={ui.heading}>Password changed</Text>
      <Text style={ui.text}>Your password was updated and existing BACity sessions were signed out.</Text>
      <Button title="Log in with your new password" onPress={() => router.replace({ pathname: '/auth', params: { mode: 'login' } })} />
    </Card>;
  }
  if (state === 'invalid' || state === 'expired' || state === 'used') {
    const message = state === 'expired'
      ? 'This reset link has expired.'
      : state === 'used'
        ? 'This reset link has already been used.'
        : 'This reset link is invalid.';
    return <Card>
      <Text style={ui.heading}>Reset link unavailable</Text>
      <Text style={ui.text}>{message} Request a new link to continue.</Text>
      <Button title="Request a new reset link" onPress={() => router.replace({ pathname: '/account', params: { action: 'forgot' } })} />
      <Pressable accessibilityRole="button" onPress={() => router.replace({ pathname: '/auth', params: { mode: 'login' } })} style={styles.textAction}>
        <Text style={styles.textActionLabel}>Back to login</Text>
      </Pressable>
    </Card>;
  }

  return <Card>
    <Text style={ui.heading}>Choose a new password</Text>
    <Text style={ui.text}>Use at least 8 characters. Spaces, Unicode, and long passphrases are supported.</Text>
    <Field label="New password" secure={!showPasswords} value={password} onChange={setPassword} />
    <Field label="Confirm password" secure={!showPasswords} value={confirmation} onChange={setConfirmation} />
    <Pressable accessibilityRole="button" onPress={() => setShowPasswords((current) => !current)} style={styles.textAction}>
      <Text style={styles.textActionLabel}>{showPasswords ? 'Hide passwords' : 'Show passwords'}</Text>
    </Pressable>
    <Notice text={notice} />
    {state === 'error' && <Button title="Check link again" onPress={inspectToken} />}
    <Button busy={state === 'submitting'} title="Set new password" onPress={submit} />
  </Card>;
}

export default function Account() {
  const { action, token } = useLocalSearchParams<{ action?: string; token?: string }>();
  const { user, refreshUser, logout } = useAuthStore();
  const [name, setName] = useState(user?.display_name ?? '');
  const [bio, setBio] = useState(user?.bio ?? '');
  const [neighborhood, setNeighborhood] = useState(user?.neighborhood ?? '');
  const [interests, setInterests] = useState(user?.interests.join(', ') ?? '');
  const [isPublic, setPublic] = useState(user?.public_profile ?? true);
  const [messages, setMessages] = useState(user?.allow_general_messages ?? false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  async function run(fn: () => Promise<unknown>, success: string) {
    setBusy(true); setNotice('');
    try { await fn(); setNotice(success); } catch (e: any) { setNotice(e.message); } finally { setBusy(false); }
  }
  async function chooseAvatar() {
    setBusy(true); setNotice('');
    try {
      const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!permission.granted) throw new Error('Photo-library permission is required.');
      const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ImagePicker.MediaTypeOptions.Images, allowsEditing: true, aspect: [1, 1], quality: 0.85 });
      if (result.canceled) return;
      await uploadAvatar(result.assets[0]);
      await refreshUser();
      setNotice('Profile photo updated.');
    } catch (e: any) { setNotice(e.message); } finally { setBusy(false); }
  }
  if (action === 'reset') {
    return <Page title="Reset password"><ResetPassword token={token ?? ''} /></Page>;
  }

  if (action === 'verify' && token) {
    return <Page title="Verify email">
      <Notice text={notice} />
      <Card>
        <Text style={ui.heading}>Confirm your email</Text>
        <Text style={ui.text}>Verify your email address to contribute to BACity.</Text>
        <Button busy={busy} title="Verify email" onPress={() => run(async () => {
          await apiRequest('/auth/verify-email', { method: 'POST', body: { token } });
          await refreshUser();
        }, 'Email verified. You can now sign in or return to BACity.')} />
        <Button title="Go to login" onPress={() => router.replace({ pathname: '/auth', params: { mode: 'login' } })} />
      </Card>
    </Page>;
  }

  if (!user) {
    return <Page title="Account recovery"><ForgotPassword /></Page>;
  }

  return <Page title="Your account">
    <Notice text={notice} />
    <Button title="Privacy & account rights" onPress={() => router.push('/privacy')} />
    {!user.email_verified && <Card><Text style={ui.text}>Verify your email before submitting, following, or messaging.</Text><Button title="Resend verification email" busy={busy} onPress={() => run(() => apiRequest('/auth/request-verification', { method: 'POST', auth: true }), 'Verification email queued.')} /><Button title="I verified my email — refresh" busy={busy} onPress={() => run(refreshUser, 'Account refreshed.')} /></Card>}
<Disclosure title="Profile photo" icon="camera-outline"><Text style={ui.text}>Choose a photo, then crop and position it in the square editor.</Text><Button title="Choose and crop photo" busy={busy} onPress={chooseAvatar} /></Disclosure>
      <Disclosure title="Identity & interests" icon="person-outline" initiallyOpen><Field label="Display name" value={name} onChange={setName} /><Field label="Bio" value={bio} onChange={setBio} multiline /><Field label="Neighborhood" value={neighborhood} onChange={setNeighborhood} /><Text style={ui.heading}>Your city interests</Text><InterestPicker choices={INTERESTS} selected={interests.split(',').map(value => value.trim()).filter(Boolean)} onToggle={category => { const current = interests.split(',').map(value => value.trim()).filter(Boolean); setInterests((current.includes(category) ? current.filter(value => value !== category) : [...current, category]).join(', ')); }} /><Disclosure title="Other interests" icon="add-outline"><Field label="Other interests (comma separated)" value={interests} onChange={setInterests} /></Disclosure><Text style={ui.text}>Public profile</Text><Switch accessibilityLabel="Public profile" value={isPublic} onValueChange={setPublic} /><Text style={ui.text}>Allow messages from people you do not follow</Text><Switch accessibilityLabel="Allow general messages" value={messages} onValueChange={setMessages} /><Button title="Save preferences" busy={busy} onPress={() => run(async () => { await apiRequest('/community/profile', { method: 'PATCH', auth: true, body: { display_name: name || null, bio, neighborhood, interests: interests.split(',').map(i => i.trim()).filter(Boolean), public_profile: isPublic, allow_general_messages: messages } }); await refreshUser(); }, 'Preferences saved.')} /></Disclosure>
<Disclosure title="Your data" icon="download-outline"><Text style={ui.text}>Export a portable JSON copy of your profile, activity, contributions, messages, and linked sign-in providers.</Text><Button title="Export my data" busy={busy} onPress={() => run(async () => { const data = await apiRequest('/community/account/export', { auth: true }); await Share.share({ title: 'BACity account export', message: JSON.stringify(data, null, 2) }); }, 'Account export prepared.')} /></Disclosure>
<Disclosure title="Delete account" icon="warning-outline"><Text style={ui.text}>This disables your account, removes private messages and profile details, and retains published contributions under a deleted-account identity.</Text>{confirmDelete ? <><Button title="Delete my account permanently" busy={busy} onPress={() => run(async () => { await apiRequest('/community/account', { method: 'DELETE', auth: true, body: { reason: 'User requested account deletion' } }); await logout(); }, 'Account deleted.')} /><Button title="Keep account" onPress={() => setConfirmDelete(false)} /></> : <Button title="Review account deletion" onPress={() => setConfirmDelete(true)} />}</Disclosure>
  </Page>;
}

const styles = StyleSheet.create({
  loading: { minHeight: 92, alignItems: 'center', justifyContent: 'center', gap: 12 },
  textAction: { minHeight: 44, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 12 },
  textActionLabel: { color: colors.primaryDark, fontFamily: fonts.semibold, fontWeight: '600', fontSize: 12 },
});
