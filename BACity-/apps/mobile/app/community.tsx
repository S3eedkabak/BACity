import { useEffect, useState } from 'react';
import { Text, View, Linking } from 'react-native';
import { router } from 'expo-router';
import { apiRequest } from '../src/api/client';
import { useAuthStore } from '../src/store/authStore';
import { Page, Card, Field, Button, Chip, Notice, ui } from '../src/components/CommunityUI';

const sections = { recommendations: 'For you', utilities: 'City utilities', places: 'Places', people: 'People', organizations: 'Organizers', submissions: 'Your contributions', notifications: 'Notifications', collections: 'Collections', follows: 'Following', blocks: 'Blocked users', moderation: 'Review queue', reports: 'Reports' };
type Section = keyof typeof sections;
const paths: Record<Section, string> = { recommendations: '/recommendations', utilities: '/community/utilities', places: '/community/places', people: '/community/people', organizations: '/community/organizations', submissions: '/community/submissions', notifications: '/community/notifications', collections: '/community/collections', follows: '/community/follows', blocks: '/community/blocks', moderation: '/community/moderation/submissions', reports: '/community/moderation/reports' };

export default function Community() {
  const user = useAuthStore(s => s.user);
  const [section, setSection] = useState<Section>('utilities');
  const [items, setItems] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [reason, setReason] = useState('');
  const [utilityKind, setUtilityKind] = useState('toilet');
  const [orgName, setOrgName] = useState('');
  const [website, setWebsite] = useState('');
  const [evidence, setEvidence] = useState('');
  const [query, setQuery] = useState('');
  const moderator = user && ['ADMIN', 'MODERATOR'].includes(user.role);
  async function load() {
    setBusy(true); setNotice(''); setItems([]);
    try { setItems(await apiRequest<any[]>(paths[section], { auth: true, params: section === 'utilities' ? { kind: utilityKind } : ['people', 'places', 'organizations'].includes(section) ? { q: query } : undefined })); }
    catch (e: any) { setNotice(e.status === 401 ? 'Sign in to see this section.' : e.message); }
    finally { setBusy(false); }
  }
  useEffect(() => { void load(); }, [section, user?.id]);
  async function act(path: string, body?: unknown, method: 'POST' | 'DELETE' = 'POST') {
    setBusy(true); setNotice('');
    try { await apiRequest(path, { auth: true, method, body }); await load(); setNotice('Saved.'); }
    catch (e: any) { setNotice(e.message); } finally { setBusy(false); }
  }
  return <Page title="Your Bratislava">
    <Text style={ui.text}>Discover local places, contribute useful information, and connect with your neighborhood.</Text>
    <Button title="Add an event, place, or utility" onPress={() => router.push('/contribute')} />
    <View style={ui.row}>{(Object.keys(sections) as Section[]).filter(s => moderator || !['moderation', 'reports'].includes(s)).map(s => <Chip key={s} title={sections[s]} active={section === s} onPress={() => { setQuery(''); setSection(s); }} />)}</View>
    {section === 'utilities' && <Field label="Utility kind (toilet, water_fountain, wifi, bench…)" value={utilityKind} onChange={setUtilityKind} />}
    {['people', 'places', 'organizations'].includes(section) && <Field label="Search by name" value={query} onChange={setQuery} />}
    <Button title={busy ? 'Loading…' : 'Refresh results'} busy={busy} onPress={load} />
    <Notice text={notice} />
    {['moderation', 'reports', 'submissions'].includes(section) && <Field label="Reason for your decision or appeal" value={reason} onChange={setReason} multiline />}
    {!busy && !items.length && <Text style={ui.muted}>Nothing here yet. Check back after contributions have been reviewed.</Text>}
    {items.map((item, index) => <Card key={item.id ?? item.event?.id ?? index}>
      <Text style={ui.heading}>{item.name ?? item.display_name ?? item.title ?? item.event?.title ?? item.payload?.title ?? item.payload?.name ?? item.kind ?? item.target_type ?? 'Update'}</Text>
      {section === 'recommendations' && <><Text style={ui.text}>{item.reasons.join(' · ')}</Text><Button title="View event" onPress={() => router.push(`/event/${item.event.id}`)} /></>}
      {section === 'people' && <><Text style={ui.muted}>{item.neighborhood} · {item.reputation_level}</Text><Button title="View profile" onPress={() => router.push(`/member/${item.id}`)} /></>}
      {['utilities', 'places'].includes(section) && <><Text style={ui.text}>{item.address}</Text><Text style={ui.muted}>{item.operational_status.replaceAll('_', ' ')} · {item.last_confirmed_at ? 'Confirmed ' + new Date(item.last_confirmed_at + (item.last_confirmed_at.endsWith('Z') ? '' : 'Z')).toLocaleDateString() : 'No recent confirmation'}</Text><Text style={ui.text}>{item.opening_hours ?? 'Opening hours unknown'}{item.free != null ? (item.free ? ' · Free' : ' · May charge a fee') : ''}{item.wheelchair_accessible != null ? (item.wheelchair_accessible ? ' · Wheelchair accessible' : ' · Not wheelchair accessible') : ''}</Text><Button title="Open location on map" onPress={() => Linking.openURL(`https://www.openstreetmap.org/?mlat=${item.latitude}&mlon=${item.longitude}#map=18/${item.latitude}/${item.longitude}`)} />{section === 'utilities' ? <View style={ui.row}>{['open', 'closed', 'out_of_order'].map(status => <Button key={status} busy={busy} title={'Confirm ' + status.replaceAll('_', ' ')} onPress={() => act(`/community/utilities/${item.id}/confirm`, { operational_status: status })} />)}</View> : <Button title="Reviews and details" onPress={() => router.push(`/place/${item.id}`)} />}</>}
      {section === 'notifications' && <><Text style={ui.text}>{item.body}</Text>{item.kind === 'message' && <Button title="Open conversation" onPress={() => router.push(`/member/${item.target_id}`)} />}{!item.read_at && <Button title="Mark read" busy={busy} onPress={() => act(`/community/notifications/${item.id}/read`)} />}</>}
      {['submissions', 'moderation'].includes(section) && <><Text style={ui.muted}>{item.state} · {item.kind}</Text><Text style={ui.text}>{item.payload?.description ?? item.payload?.reason ?? item.payload?.address}</Text>{item.payload?.source_url && <Button title="Check original source" onPress={() => Linking.openURL(item.payload.source_url)} />}{item.payload?.evidence_url && <Button title="Check ownership evidence" onPress={() => Linking.openURL(item.payload.evidence_url)} />}<Notice text={item.decision_reason} /><Notice text={item.appeal ? 'Appeal: ' + item.appeal : ''} />{section === 'moderation' && <><Text style={ui.muted}>{item.risk_flags.join(' · ')}</Text><View style={ui.row}>{['approve', 'reject'].map(decision => <Button key={decision} title={decision === 'approve' ? 'Approve' : 'Reject'} busy={busy} onPress={() => act(`/community/moderation/submissions/${item.id}`, { decision, reason })} />)}</View></>}{section === 'submissions' && item.state === 'rejected' && !item.appeal && <Button title="Appeal decision" busy={busy} onPress={() => act(`/community/submissions/${item.id}/appeal`, { reason })} />}</>}
      {section === 'reports' && <><Text style={ui.text}>{item.reason}</Text><Text style={ui.muted}>Reported {item.target_type}</Text><Button title="Uphold report and restrict content" busy={busy} onPress={() => act(`/community/moderation/reports/${item.id}`, { decision: 'approve', reason })} /><Button title="Dismiss report" busy={busy} onPress={() => act(`/community/moderation/reports/${item.id}`, { decision: 'reject', reason })} /></>}
      {section === 'organizations' && <><Text style={ui.text}>{item.description}</Text><Text style={ui.muted}>{item.verified ? 'Verified organizer' : 'Unverified organizer'}</Text><Button title="Follow organizer" busy={busy} onPress={() => act('/community/follows', { target_type: 'organizer', target_id: item.id })} /><Field label="Public evidence of your ownership (HTTPS)" value={evidence} onChange={setEvidence} /><Button title="Request ownership review" busy={busy} onPress={() => act(`/community/organizations/${item.id}/claim`, { evidence_url: evidence, reason: 'Please verify my ownership using the supplied public evidence' })} /></>}
      {section === 'collections' && <><Text style={ui.text}>{item.description}</Text>{item.items.map((entry: any) => <Button key={entry.id} title={'Open ' + entry.type} onPress={() => entry.type === 'event' ? router.push(`/event/${entry.id}`) : entry.type === 'place' ? router.push(`/place/${entry.id}`) : setSection('utilities')} />)}</>}
      {section === 'follows' && <><Text style={ui.text}>{item.target_id}</Text><Button title="Unfollow" busy={busy} onPress={() => act(`/community/follows/${item.id}`, undefined, 'DELETE')} /></>}
      {section === 'blocks' && <><Text style={ui.text}>{item.blocked_id}</Text><Button title="Unblock" busy={busy} onPress={() => act(`/community/blocks/${item.blocked_id}`, undefined, 'DELETE')} /></>}
    </Card>)}
    {section === 'organizations' && <Card><Text style={ui.heading}>Register your organization</Text><Field label="Organization name" value={orgName} onChange={setOrgName} /><Field label="Official website (HTTPS)" value={website} onChange={setWebsite} /><Button title="Create organization page" busy={busy} onPress={() => act('/community/organizations', { name: orgName, website })} /><Button title="Manage your verified organizations" onPress={() => router.push('/organizer')} /></Card>}
  </Page>;
}
