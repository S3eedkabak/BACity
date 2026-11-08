import { useThemeRevision } from '../../src/theme/appearance';
import { FollowAction } from '../../src/components/interactions/FollowAction';
import { useQuery } from '@tanstack/react-query';
import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Text } from 'react-native';
import { externalLinking as Linking } from '../../src/api/externalLinking';
import { apiRequest } from '../../src/api/client';
import { EventOut } from '../../src/types/event';
import { EventCard } from '../../src/components/EventCard';
import { Page, Card, Button, Notice, ui } from '../../src/components/CommunityUI';
export default function Venue() {
  useThemeRevision();
  const { id } = useLocalSearchParams<{ id: string }>();
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const query = useQuery({ queryKey: ['venue', id], queryFn: async () => {
    const [venue, events] = await Promise.all([apiRequest<any>(`/venues/${id}`), apiRequest<EventOut[]>(`/venues/${id}/events`)]);
    return { venue, events };
  } });
  return <Page title={query.data?.venue.name ?? 'Venue'}><Notice text={notice || query.error?.message} />{query.isPending && <Text style={ui.text}>Loading venue…</Text>}{query.isError && <Button title="Try again" onPress={() => { void query.refetch(); }} />}{query.data && <><Card><Text style={ui.text}>{query.data.venue.address}</Text>{query.data.venue.website && <Button title="Visit website" onPress={() => Linking.openURL(query.data!.venue.website)} />}<FollowAction type="venue" id={id} /></Card><Text style={ui.heading}>Events here</Text>{!query.data.events.length && <Text style={ui.muted}>No events listed.</Text>}{query.data.events.map(event => <EventCard key={event.id} event={event} />)}</>}</Page>;
}
