import { useEffect, useState } from 'react';
import { Text } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { apiRequest } from '../../src/api/client';
import { Page, Card, Notice, ui } from '../../src/components/CommunityUI';
import { Discussion } from '../../src/components/Discussion';

export default function Place() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [place, setPlace] = useState<any>(null);
  const [error, setError] = useState('');
  useEffect(() => { apiRequest(`/community/places/${id}`).then(setPlace).catch(e => setError(e.message)); }, [id]);
  return <Page title={place?.name ?? 'Place'}><Notice text={error} />{place && <><Card><Text style={ui.text}>{place.description}</Text><Text style={ui.text}>{place.address}</Text><Text style={ui.muted}>{place.trust_level} · {place.operational_status}</Text></Card><Discussion id={id} kind="place" /></>}</Page>;
}
