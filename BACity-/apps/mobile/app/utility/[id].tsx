import { useQuery } from '@tanstack/react-query';
import { useLocalSearchParams, router } from 'expo-router';
import { Text } from 'react-native';
import { apiRequest } from '../../src/api/client';
import { Page, Card, Button, Notice, ui } from '../../src/components/CommunityUI';
export default function Utility() {
  const { id, kind } = useLocalSearchParams<{ id: string; kind?: string }>();
  const query = useQuery({ queryKey: ['utility', id, kind], queryFn: async () => {
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
  return <Page title={item?.name ?? 'City utility'}><Notice text={query.error?.message} />{query.isPending && <Text style={ui.text}>Loading utility…</Text>}{query.isError && <Button title="Try again" onPress={() => { void query.refetch(); }} />}{item && <Card><Text style={ui.text}>{item.address}</Text><Text style={ui.text}>{item.opening_hours ?? 'Opening hours unknown'}</Text><Text style={ui.muted}>{item.operational_status}</Text><Button title="Confirm status in Community" onPress={() => router.push({ pathname: '/community', params: { section: 'utilities', kind: item.kind } })} /><Button title="Suggest a correction" onPress={() => router.push({ pathname: '/correction', params: { type: 'utility', id } })} /><Button title="Create a collection with this utility" onPress={() => router.push({ pathname: '/collection', params: { type: 'utility', id } })} /></Card>}</Page>;
}
