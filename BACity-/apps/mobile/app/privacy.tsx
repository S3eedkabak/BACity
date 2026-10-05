import { useEffect, useState } from 'react';
import { Share, Text, View } from 'react-native';
import { router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { Page, Card, Disclosure, Button, Chip, Field, Notice, ui } from '../src/components/CommunityUI';
import { apiRequest } from '../src/api/client';
import { externalLinking } from '../src/api/externalLinking';
import { privacyApi, privacyKinds, PrivacyKind } from '../src/api/privacy';
import { useAuthStore } from '../src/store/authStore';

export default function Privacy() {
  const owner = useAuthStore(state => state.user?.id);
  return <PrivacyContent key={owner || 'guest'} />;
}

function PrivacyContent() {
  const user = useAuthStore(state => state.user);
  const [kind, setKind] = useState<PrivacyKind>('ACCESS');
  const [details, setDetails] = useState('');
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  useEffect(() => { setDetails(''); setNotice(''); setOffset(0); setBusy(false); }, [user?.id]);
  const info = useQuery({ queryKey: ['privacy-information'], queryFn: privacyApi.information });
  const requests = useQuery({ queryKey: ['privacy-requests', user?.id, offset], queryFn: () => privacyApi.requests(offset), enabled: !!user });
  async function shareExport(path: string, title: string) {
    const owner = user?.id;
    const data = await apiRequest(path, { auth: true });
    if (useAuthStore.getState().user?.id !== owner) throw new Error('Session changed; request your export again.');
    await Share.share({ title, message: JSON.stringify(data, null, 2) });
  }
  async function run(action: () => Promise<unknown>) {
    const owner = user?.id;
    setBusy(true); setNotice('');
    try {
      await action();
      if (useAuthStore.getState().user?.id === owner) { setNotice('Done.'); setDetails(''); void requests.refetch(); }
    } catch (error: any) { if (useAuthStore.getState().user?.id === owner) setNotice(error.message); }
    finally { if (useAuthStore.getState().user?.id === owner) setBusy(false); }
  }
  return <Page title="Privacy & account rights">
    <Notice text={notice} />
    <Disclosure title="Privacy information" initiallyOpen>
      {info.isLoading ? <Text style={ui.text}>Loading privacy information…</Text> : info.isError ? <Button title="Retry privacy information" onPress={() => { void info.refetch(); }} /> : <>
        <Text style={ui.text}>{info.data?.message_encryption}</Text>
        <Text style={ui.text}>{info.data?.location}</Text>
        <Text style={ui.text}>{info.data?.recommendations}</Text>
        {info.data?.controller_legal_name && <Text selectable style={ui.text}>Controller/trader: {info.data.controller_legal_name}</Text>}
        {info.data?.business_address && <Text selectable style={ui.text}>Business address: {info.data.business_address}</Text>}
        {info.data?.support_contact_email && <Text selectable style={ui.text}>Support contact: {info.data.support_contact_email}</Text>}
        {info.data?.legal_contact_email && <Text selectable style={ui.text}>Legal contact: {info.data.legal_contact_email}</Text>}
        {!info.data?.documents_ready && <Text style={ui.text}>Published privacy documents and contact details are not yet configured. This is a pre-production limitation.</Text>}
        {info.data?.privacy_notice_url && <Button title={`Privacy notice${info.data.privacy_notice_version ? ` (${info.data.privacy_notice_version})` : ''}`} onPress={() => { void externalLinking.openURL(info.data!.privacy_notice_url!); }} />}
        {info.data?.terms_url && <Button title="Terms" onPress={() => { void externalLinking.openURL(info.data!.terms_url!); }} />}
        {info.data?.privacy_contact_email && <Text selectable style={ui.text}>Privacy contact: {info.data.privacy_contact_email}. Non-account requests may use this contact.</Text>}
      </>}
    </Disclosure>
    {!user ? <Card><Text style={ui.text}>Sign in to use account controls and track a privacy request. Non-account requests use the published privacy contact when configured.</Text><Button title="Sign in" onPress={() => router.push('/auth')} /></Card> : <>
      <Disclosure title="Your controls">
        <Button title="Edit profile, privacy preferences or delete account" onPress={() => router.push('/account')} />
        <Button title="Location preferences" onPress={() => router.push('/(tabs)/discover')} />
        <Text style={ui.text}>Home location controls let you turn recommendation location off. Saved Area Watches are separate and can be deleted individually.</Text>
        <Button title="Manage Area Watches" onPress={() => router.push('/area-watches')} />
        <Button title="Export all account data (JSON)" busy={busy} onPress={() => { void run(() => shareExport('/community/account/export', 'BACity access export')); }} />
        <Button title="Export user-provided data (JSON)" busy={busy} onPress={() => { void run(() => shareExport('/privacy/portability', 'BACity portability data')); }} />
        <Text style={ui.text}>Sharing an export sends it to the app or destination you choose. Keep it private.</Text>
      </Disclosure>
      <Disclosure title="Request human privacy review"><Text style={ui.text}>Requests are assessed, not automatically granted. Do not include passwords, identity documents or other people's private information. Account access is verified; reviewers may request proportionate additional information.</Text>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>{privacyKinds.map(value => <Chip key={value} title={value.replaceAll('_', ' ')} active={kind === value} onPress={() => setKind(value)} />)}</View>
        <Field label="Request details (optional, maximum 2000 characters)" value={details} onChange={value => setDetails(value.slice(0, 2000))} multiline />
        <Button title="Submit privacy request" busy={busy} onPress={() => { void run(() => privacyApi.submit(kind, details)); }} />
      </Disclosure>
      <Disclosure title="Your request status">
        {requests.isLoading ? <Text style={ui.text}>Loading requests…</Text> : requests.isError ? <Button title="Retry requests" onPress={() => { void requests.refetch(); }} /> : requests.data?.length ? requests.data.map(item => <View key={item.id} style={{ marginBottom: 12 }}><Text style={ui.text}>{item.kind.replaceAll('_', ' ')} · {item.status.replaceAll('_', ' ')}</Text><Text style={ui.text}>Target response: {new Date(item.due_at + 'Z').toLocaleDateString()}{item.extended ? ' (assessed extension)' : ''}{item.overdue ? ' · Awaiting response' : ''}</Text>{item.response ? <Text style={ui.text}>{item.response}</Text> : null}</View>) : <Text style={ui.text}>No requests on this page.</Text>}
        {offset > 0 && <Button title="Previous requests" onPress={() => setOffset(value => Math.max(0, value - 20))} />}
        {requests.data?.length === 20 && <Button title="More requests" onPress={() => setOffset(value => value + 20)} />}
        <Button title="Refresh status" onPress={() => { void requests.refetch(); }} />
      </Disclosure>
      {user.role === 'ADMIN' && <Button title="Admin privacy request review" onPress={() => router.push('/privacy-admin')} />}
    </>}
  </Page>;
}
