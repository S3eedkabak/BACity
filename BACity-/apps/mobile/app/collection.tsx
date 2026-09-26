import { useEffect, useState } from 'react';
import { Text, Switch } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { apiRequest } from '../src/api/client';
import { Page, Card, Field, Button, Notice, ui } from '../src/components/CommunityUI';

type Item = { type: string; id: string; name: string };
export default function Collection() {
  const params = useLocalSearchParams<{ type?: string; id?: string }>();
  const [items, setItems] = useState<Item[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [query, setQuery] = useState('');
  const [isPublic, setPublic] = useState(false);
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const key = (item: Item) => item.type + ':' + item.id;
  useEffect(() => {
    let active = true;
    Promise.all([apiRequest<any>('/events', { params: { limit: 100 } }), apiRequest<any[]>('/community/places'), Promise.all(['toilet', 'water_fountain', 'bike_repair', 'charging', 'wifi', 'bench', 'playground', 'dog_park', 'recycling', 'accessible_entrance', 'parking', 'locker'].map(kind => apiRequest<any[]>('/community/utilities', { params: { kind } }))).then(groups => groups.flat())])
      .then(([events, places, utilities]) => {
        if (!active) return;
        const choices: Item[] = [...events.items.map((i: any) => ({ type: 'event', id: i.id, name: i.title })), ...places.map(i => ({ type: 'place', id: i.id, name: i.name })), ...utilities.map(i => ({ type: 'utility', id: i.id, name: i.name }))];
        if (params.id && params.type && ['event', 'place', 'utility'].includes(params.type)) {
          const item = { type: params.type, id: params.id, name: 'Item you opened' };
          if (!choices.some(i => key(i) === key(item))) choices.unshift(item);
          setSelected([key(item)]);
        }
        setItems(choices);
      }).catch(e => active && setNotice(e.message));
    return () => { active = false; };
  }, [params.id, params.type]);
  async function save() {
    setBusy(true); setNotice('');
    try {
      await apiRequest('/community/collections', { method: 'POST', auth: true, body: { title, description, public: isPublic, items: items.filter(i => selected.includes(key(i))).map(({ type, id }) => ({ type, id })) } });
      router.replace('/collections');
    } catch (e: any) { setNotice(e.message); } finally { setBusy(false); }
  }
  return <Page title="Create a collection"><Notice text={notice} /><Card><Field label="Title" value={title} onChange={setTitle} /><Field label="Description" value={description} onChange={setDescription} multiline /><Text style={ui.text}>Share publicly</Text><Switch accessibilityLabel="Share publicly" value={isPublic} onValueChange={setPublic} /><Text style={ui.muted}>{selected.length} selected</Text><Button title="Save collection" busy={busy} onPress={save} /></Card><Field label="Filter available events, places and utilities" value={query} onChange={setQuery} />{items.filter(i => i.name.toLowerCase().includes(query.toLowerCase())).map(item => <Button key={key(item)} title={`${selected.includes(key(item)) ? '✓ ' : ''}${item.name} (${item.type})`} onPress={() => setSelected(current => current.includes(key(item)) ? current.filter(k => k !== key(item)) : [...current, key(item)])} />)}</Page>;
}
