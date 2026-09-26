import { useQuery } from '@tanstack/react-query';
import { useLocalSearchParams, router } from 'expo-router';
import { Text } from 'react-native';
import { useState } from 'react';
import { apiRequest } from '../../src/api/client';
import { Page, Card, Button, Notice, ui } from '../../src/components/CommunityUI';
export default function Utility() {
  const { id, kind } = useLocalSearchParams<{ id: string; kind?: string }>();
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const query = useQuery({ queryKey: ['utility', id, kind], queryFn: async () => {
    if (id) return apiRequest<any>(`/community/utilities/${id}`);
    const kinds = kind ? [kind] : ['toilet', 'water_fountain', 'bike_repair', 'charging', 'wifi', 'bench', 'playground', 'dog_park', 'recycling', 'accessible_entrance', 'parking', 'locker'];
    for (const utilityKind of kinds) {
      let offset = 0;
      while (true) {
        const rows = await apiRequest<any[]>('/community/utilities', { params: { kind: utilityKind, offset } });
        const item = rows.find(row => row.id === id);
        if (item) return item;
        if (rows.length < 100) break;
        offset += rows.length;
      }
    }
    throw new Error('Utility not found.');
  } });
  const item = query.data;
  async function confirm(status: string) { setBusy(true); setNotice(''); try { await apiRequest(`/community/utilities/${id}/confirm`, { method: 'POST', auth: true, body: { operational_status: status } }); setNotice('Status confirmation saved.'); await query.refetch(); } catch (e: any) { setNotice(e.message); } finally { setBusy(false); } }
  return <Page title={item?.name ?? 'City utility'}><Notice text={notice || query.error?.message} />{query.isPending && <Text style={ui.text}>Loading utility…</Text>}{query.isError && <Button title="Try again" onPress={() => { void query.refetch(); }} />}{item && <Card><Text style={ui.text}>{item.address ?? 'Address not supplied by the city dataset'}</Text><Text style={ui.text}>{item.opening_hours ?? 'Opening hours unknown'}</Text><Text style={ui.muted}>{item.operational_status.replaceAll('_', ' ')} · {item.freshness_status} · {Math.round(item.confidence_score * 100)}% confidence</Text><Text style={ui.muted}>{item.confirmation_count} recent confirmation{item.confirmation_count === 1 ? '' : 's'}{item.status_conflict ? ' · conflicting reports' : ''}</Text>{['open', 'closed', 'out_of_order'].map(status => <Button key={status} busy={busy} title={`Confirm ${status.replaceAll('_', ' ')}`} onPress={() => confirm(status)} />)}<Button title="Suggest a correction" onPress={() => router.push({ pathname: '/correction', params: { type: 'utility', id } })} /><Button title="Create a collection with this utility" onPress={() => router.push({ pathname: '/collection', params: { type: 'utility', id } })} /></Card>}</Page>;
}
