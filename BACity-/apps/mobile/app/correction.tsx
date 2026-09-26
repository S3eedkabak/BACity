import { useState } from 'react';
import { useLocalSearchParams, router } from 'expo-router';
import { Text, View } from 'react-native';
import { apiRequest } from '../src/api/client';
import { Page, Card, Field, Button, Chip, Notice, ui } from '../src/components/CommunityUI';
export default function Correction() {
  const { type, id } = useLocalSearchParams<{ type: string; id: string }>();
  const [field, setField] = useState('address');
  const [value, setValue] = useState('');
  const [reason, setReason] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const fields = type === 'event' ? ['title', 'description', 'address', 'latitude', 'longitude', 'image_url', 'ticket_url', 'neighborhood'] : type === 'place' ? ['name', 'description', 'address', 'latitude', 'longitude', 'website', 'neighborhood'] : ['name', 'address', 'latitude', 'longitude', 'opening_hours', 'source_url'];
  async function submit() {
    setBusy(true); setNotice('');
    try {
      const numeric = ['latitude', 'longitude'].includes(field);
      if (!value.trim() || (numeric && !Number.isFinite(Number(value)))) throw new Error('Enter a valid replacement value.');
      await apiRequest('/community/submissions/corrections', { method: 'POST', auth: true, body: { target_type: type, target_id: id, reason, changes: { [field]: numeric ? Number(value) : value } } });
      router.replace('/activity');
    } catch (e: any) { setNotice(e.message); } finally { setBusy(false); }
  }
  return <Page title="Suggest a correction"><Notice text={notice} />{id && ['event', 'place', 'utility'].includes(type) ? <Card><Text style={ui.text}>Choose what needs updating. A moderator will review your suggestion.</Text><View style={ui.row}>{fields.map(f => <Chip key={f} title={f.replaceAll('_', ' ')} active={field === f} onPress={() => { setField(f); setValue(''); }} />)}</View><Field label="Correct value" value={value} onChange={setValue} /><Field label="Reason and supporting evidence" value={reason} onChange={setReason} multiline /><Button title="Submit correction" busy={busy} onPress={submit} /></Card> : <Text style={ui.text}>Open an event, place or utility to suggest a correction.</Text>}</Page>;
}
