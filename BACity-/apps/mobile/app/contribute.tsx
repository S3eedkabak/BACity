import { useState } from 'react';
import { Text, View, Switch } from 'react-native';
import { router } from 'expo-router';
import { apiRequest } from '../src/api/client';
import { Page, Card, Field, Button, Notice, ui } from '../src/components/CommunityUI';
import { useAuthStore } from '../src/store/authStore';

export default function Contribute() {
  const user = useAuthStore(s => s.user);
  const [kind, setKind] = useState<'events' | 'places' | 'utilities'>('events');
  const [fields, setFields] = useState<Record<string, string>>({ category: 'Community', utility: 'toilet' });
  const [free, setFree] = useState(false);
  const [accessible, setAccessible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  function field(key: string, label: string, multiline = false) { return <Field key={key} label={label} value={fields[key] ?? ''} onChange={value => setFields({ ...fields, [key]: value })} multiline={multiline} />; }
  async function submit() {
    setBusy(true); setNotice('');
    try {
      const coords = { latitude: fields.latitude ? Number(fields.latitude) : null, longitude: fields.longitude ? Number(fields.longitude) : null };
      let body: Record<string, unknown>;
      if (kind === 'events') {
        if (!fields.start_time || !/([+-]\d\d:\d\d|Z)$/.test(fields.start_time)) throw new Error('Include the timezone offset, for example 2026-12-10T19:00+01:00.');
        body = { ...coords, title: fields.name, description: fields.description, address: fields.address, start_time: fields.start_time, end_time: fields.end_time || null, category: fields.category, source_url: fields.source_url, image_url: fields.image_url || null, ticket_url: fields.ticket_url || null, price: fields.price ? Number(fields.price) : null, neighborhood: fields.neighborhood || null };
      } else if (kind === 'places') {
        body = { ...coords, name: fields.name, description: fields.description, address: fields.address, category: fields.category, neighborhood: fields.neighborhood || null, website: fields.source_url || null, accessibility: { wheelchair: accessible } };
      } else {
        body = { ...coords, name: fields.name, kind: fields.utility, address: fields.address, source_url: fields.source_url || null, opening_hours: fields.opening_hours || null, free, wheelchair_accessible: accessible };
      }
      await apiRequest('/community/submissions/' + kind, { method: 'POST', auth: true, body });
      setNotice('Submitted for review. Track the decision in Community → Your contributions.');
      setFields({ category: 'Community', utility: 'toilet' });
    } catch (e: any) { setNotice(e.message); } finally { setBusy(false); }
  }
  return <Page title="Add to your city">
    <Text style={ui.text}>Share a local event, place, or useful facility. A moderator reviews every community submission before it appears publicly.</Text>
    {!user?.email_verified ? <Card><Text style={ui.text}>Sign in and verify your email to contribute.</Text><Button title="Account settings" onPress={() => router.push('/account')} /></Card> : <>
      <View style={ui.row}>{(['events', 'places', 'utilities'] as const).map(k => <Button key={k} title={(kind === k ? '✓ ' : '') + k} onPress={() => setKind(k)} />)}</View>
      <Card>{field('name', kind === 'events' ? 'Event title' : 'Name')}{kind !== 'utilities' && field('description', 'Description', true)}{field('address', 'Street address in Bratislava')}{field('latitude', 'Latitude (48.00 to 48.35)')}{field('longitude', 'Longitude (16.90 to 17.35)')}{field('source_url', kind === 'events' ? 'Original event page (HTTPS, required)' : 'Source website (HTTPS, optional)')}
        {kind === 'events' && <>{field('start_time', 'Start date and time, e.g. 2026-12-10T19:00+01:00')}{field('end_time', 'End date and time (optional, with timezone)')}{field('image_url', 'Image URL (HTTPS, optional)')}{field('ticket_url', 'Ticket URL (HTTPS, optional)')}{field('price', 'Price in EUR (0 for free, blank if unknown)')}</>}
        {kind !== 'utilities' && <>{field('category', 'Category, e.g. Community, Music, Culture, Sports')}{field('neighborhood', 'Neighborhood')}</>}
        {kind === 'utilities' && <>{field('utility', 'Kind: toilet, water_fountain, bike_repair, charging, wifi, bench, playground, dog_park, recycling, accessible_entrance, parking, locker')}{field('opening_hours', 'Opening hours')}<Text style={ui.text}>Free to use</Text><Switch value={free} onValueChange={setFree} accessibilityLabel="Free to use" /></>}
        {kind !== 'events' && <><Text style={ui.text}>Wheelchair accessible</Text><Switch value={accessible} onValueChange={setAccessible} accessibilityLabel="Wheelchair accessible" /></>}
        <Button title="Submit for review" busy={busy} onPress={submit} />
      </Card>
    </>}
    <Notice text={notice} />
  </Page>;
}
