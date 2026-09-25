import { useEffect, useState } from 'react';
import { Text } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { apiRequest } from '../../src/api/client';
import { Page, Card, Field, Button, Notice, ui } from '../../src/components/CommunityUI';

export default function Member() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [profile, setProfile] = useState<any>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [body, setBody] = useState('');
  const [reason, setReason] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  async function load() {
    try { setProfile(await apiRequest(`/community/profiles/${id}`, { auth: true })); setMessages(await apiRequest<any[]>(`/community/messages/${id}`, { auth: true })); }
    catch (e: any) { setNotice(e.message); }
  }
  useEffect(() => { void load(); }, [id]);
  async function act(path: string, payload?: unknown) {
    setBusy(true); setNotice('');
    try { await apiRequest(path, { method: 'POST', auth: true, body: payload }); setBody(''); await load(); setNotice('Saved.'); }
    catch (e: any) { setNotice(e.message); } finally { setBusy(false); }
  }
  return <Page title={profile?.display_name ?? 'Community profile'}><Notice text={notice} />{profile && <>
    <Card><Text style={ui.text}>{profile.bio}</Text><Text style={ui.muted}>{profile.city} · {profile.neighborhood} · {profile.reputation_level}</Text><Text style={ui.text}>{profile.followers} followers · {profile.following} following</Text><Button title="Follow" busy={busy} onPress={() => act('/community/follows', { target_type: 'user', target_id: id })} /><Button title="Block this person" busy={busy} onPress={() => act(`/community/blocks/${id}`)} /></Card>
    <Card><Text style={ui.heading}>Conversation</Text><Text style={ui.muted}>Messages require mutual follows unless the recipient allows general messages. Messages are retained for 90 days by default.</Text>{messages.slice().reverse().map(message => <Text key={message.id} style={ui.text}>{message.sender_id === id ? profile.display_name ?? 'Them' : 'You'}: {message.body}</Text>)}<Field label="Message" value={body} onChange={setBody} multiline /><Button title="Send message" busy={busy} onPress={() => act(`/community/messages/${id}`, { body })} /><Button title="Refresh conversation" onPress={load} /></Card>
    <Card><Field label="Reason for reporting this profile" value={reason} onChange={setReason} multiline /><Button title="Report profile" busy={busy} onPress={() => act('/community/reports', { target_type: 'user', target_id: id, reason })} /></Card>
  </>}</Page>;
}
