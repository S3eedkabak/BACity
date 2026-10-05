import { useEffect, useState } from 'react';
import { Text } from 'react-native';
import { useQuery } from '@tanstack/react-query';
import { Page, Card, Button, Field, Notice, ui } from '../src/components/CommunityUI';
import { apiRequest } from '../src/api/client';
import { PrivacyRequest } from '../src/api/privacy';
import { useAuthStore } from '../src/store/authStore';

export default function PrivacyAdmin() {
  const owner = useAuthStore(state => state.user?.id);
  return <PrivacyAdminContent key={owner || 'guest'} />;
}

function PrivacyAdminContent() {
  const user = useAuthStore(state => state.user);
  const allowed = user?.role === 'ADMIN';
  const [selected, setSelected] = useState('');
  const [offset, setOffset] = useState(0);
  const [response, setResponse] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { setSelected(''); setResponse(''); setNotice(''); setOffset(0); }, [user?.id]);
  const queue = useQuery({ queryKey: ['privacy-admin', user?.id, offset], queryFn: () => apiRequest<PrivacyRequest[]>(`/privacy/admin/requests?offset=${offset}&limit=20`, { auth: true }), enabled: allowed });
  const item = useQuery({ queryKey: ['privacy-admin-detail', user?.id, selected], queryFn: () => apiRequest<PrivacyRequest>(`/privacy/admin/requests/${selected}`, { auth: true }), enabled: allowed && !!selected });
  async function review(status: string, code: string, confirmed = false, extend = false) {
    const owner = user?.id;
    setBusy(true); setNotice('');
    try {
      await apiRequest(`/privacy/admin/requests/${selected}`, { method: 'PATCH', auth: true, body: { status, decision_code: code, response, identity_confirmed: confirmed, extend } });
      if (useAuthStore.getState().user?.id === owner) { setResponse(''); void item.refetch(); void queue.refetch(); }
    } catch (error: any) { if (useAuthStore.getState().user?.id === owner) setNotice(error.message); }
    finally { if (useAuthStore.getState().user?.id === owner) setBusy(false); }
  }
  if (!allowed) return <Page title="Privacy review"><Notice text="Administrator permission required." /></Page>;
  return <Page title="Privacy request review">
    <Notice text={notice} />
    <Text style={ui.text}>Need-to-know access is audited. Identity assessment, legal exceptions and fulfilment happen through approved operational procedures, not automatically. Do not copy private data or identity documents into responses.</Text>
    {queue.isLoading ? <Text style={ui.text}>Loading queue…</Text> : queue.isError ? <Button title="Retry queue" onPress={() => { void queue.refetch(); }} /> : queue.data?.length ? queue.data.map(value => <Card key={value.id}><Text style={ui.text}>{value.kind} · {value.status} · Due {new Date(value.due_at + 'Z').toLocaleDateString()}{value.overdue ? ' · OVERDUE' : ''}</Text><Button title="Review request" onPress={() => { setSelected(value.id); setResponse(''); }} /></Card>) : <Text style={ui.text}>No requests on this page.</Text>}
    {offset > 0 && <Button title="Previous page" onPress={() => setOffset(value => Math.max(0, value - 20))} />}
    {queue.data?.length === 20 && <Button title="Next page" onPress={() => setOffset(value => value + 20)} />}
    {selected && <Card>
      {item.isLoading ? <Text style={ui.text}>Loading request…</Text> : item.isError ? <Button title="Retry request" onPress={() => { void item.refetch(); }} /> : <>
        <Text style={ui.heading}>{item.data?.kind} · {item.data?.status}</Text>
        <Text style={ui.text}>{item.data?.details || 'No additional details supplied.'}</Text>
        <Text style={ui.text}>{item.data?.response}</Text>
        <Field label="User-facing response (no third-party private information)" value={response} onChange={value => setResponse(value.slice(0, 2000))} multiline />
        <Button title="Begin review" busy={busy} onPress={() => { void review('in_review', 'information_needed'); }} />
        <Button title="Ask for proportionate additional information" busy={busy} onPress={() => { void review('awaiting_information', 'information_needed'); }} />
        <Button title="Communicate assessed extension (once, within initial month)" busy={busy} onPress={() => { void review('in_review', 'other_assessed_reason', false, true); }} />
        <Button title="Confirm identity assessed and request fulfilled" busy={busy} onPress={() => { void review('completed', 'fulfilled', true); }} />
        <Button title="Record assessed refusal with explanation" busy={busy} onPress={() => { void review('refused', 'other_assessed_reason'); }} />
      </>}
    </Card>}
  </Page>;
}
