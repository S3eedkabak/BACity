import { useEffect, useState } from 'react';
import { Text, View } from 'react-native';
import { router } from 'expo-router';
import { apiRequest } from '../api/client';
import { useAuthStore } from '../store/authStore';
import { Card, Field, Button, Chip, Notice, ui } from './CommunityUI';

export function Discussion({ id, kind }: { id: string; kind: 'event' | 'place' }) {
  const token = useAuthStore(s => s.token);
  const [reviews, setReviews] = useState<any[]>([]);
  const [comments, setComments] = useState<any[]>([]);
  const [body, setBody] = useState('');
  const [comment, setComment] = useState('');
  const [ratings, setRatings] = useState<Record<string, number>>({});
  const [reason, setReason] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const dimensions = kind === 'event' ? ['worth_attending', 'crowd', 'value', 'accessibility', 'would_attend_again'] : ['atmosphere', 'price', 'accessibility', 'cleanliness', 'crowdedness', 'family_friendliness', 'solo_friendliness'];
  async function load() {
    try { setReviews(await apiRequest<any[]>(`/community/reviews/${kind}/${id}`, { auth: true })); if (kind === 'event') setComments(await apiRequest<any[]>(`/community/events/${id}/comments`, { auth: true })); }
    catch (e: any) { setNotice(e.message); }
  }
  useEffect(() => { if (token) void load(); }, [id, token]);
  async function act(path: string, payload?: unknown) {
    setBusy(true); setNotice('');
    try { await apiRequest(path, { method: 'POST', auth: true, body: payload }); await load(); setNotice('Saved.'); }
    catch (e: any) { setNotice(e.message); } finally { setBusy(false); }
  }
  if (!token) return <Card><Text style={ui.text}>Sign in to read reviews and join the discussion.</Text><Button title="Sign in" onPress={() => router.push({ pathname: '/auth', params: { mode: 'login' } })} /></Card>;
  return <View style={{ gap: 16, padding: 14 }}><Notice text={notice} />
    <Card><Text style={ui.heading}>Community reviews</Text>{reviews.length === 0 && <Text style={ui.muted}>No reviews yet.</Text>}{reviews.map(review => <Card key={review.id}><Text style={ui.text}>{review.body}</Text><Text style={ui.muted}>{Object.entries(review.dimensions).map(([k, v]) => `${k.replaceAll('_', ' ')}: ${v}/5`).join(' · ')}</Text><Text style={ui.muted}>{review.attendance_verified ? 'Attendance verified' : 'Attendance not verified'} · {review.helpful} found this helpful</Text><Button title="Helpful" busy={busy} onPress={() => act(`/community/reviews/${review.id}/helpful`)} /><Button title="View contributor" onPress={() => router.push(`/member/${review.user_id}`)} /><Button title="Report review using reason below" busy={busy} onPress={() => act('/community/reports', { target_type: 'review', target_id: review.id, reason })} /></Card>)}
      <Field label="Your review (at least 10 characters)" value={body} onChange={setBody} multiline /><Text style={ui.muted}>Choose ratings for the aspects you experienced. Event reviews open after the event takes place.</Text>{dimensions.map(dimension => <View key={dimension} style={{ gap: 6 }}><Text style={ui.text}>{dimension.replaceAll('_', ' ')}</Text><View style={ui.row}>{[1, 2, 3, 4, 5].map(rating => <Chip key={rating} title={String(rating)} active={ratings[dimension] === rating} onPress={() => setRatings({ ...ratings, [dimension]: rating })} />)}</View></View>)}<Button title="Publish or update your review" busy={busy} onPress={() => act('/community/reviews', { target_type: kind, target_id: id, body, dimensions: ratings })} />
    </Card>
    {kind === 'event' && <Card><Text style={ui.heading}>Event discussion</Text>{comments.map(c => <Card key={c.id}><Text style={ui.text}>{c.body}</Text><Button title="View contributor" onPress={() => router.push(`/member/${c.user_id}`)} /><Button title="Report comment using reason below" busy={busy} onPress={() => act('/community/reports', { target_type: 'comment', target_id: c.id, reason })} /></Card>)}<Field label="Add a comment" value={comment} onChange={setComment} multiline /><Button title="Post comment" busy={busy} onPress={() => act(`/community/events/${id}/comments`, { body: comment })} /></Card>}
    <Card><Field label="Report reason" value={reason} onChange={setReason} multiline /><Button title={'Report this ' + kind} busy={busy} onPress={() => act('/community/reports', { target_type: kind, target_id: id, reason })} /><Button title="Refresh discussion" onPress={load} /></Card>
  </View>;
}
