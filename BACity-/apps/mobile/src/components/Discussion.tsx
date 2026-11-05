import { useThemeRevision } from '../theme/appearance';
import { useQuery } from '@tanstack/react-query';
import { getReviews, getReviewSummary } from '../api/interactions';
import { FeedbackComposer } from './interactions/FeedbackComposer';
import { StarRating } from './interactions/StarRating';
import { NumberTicker } from './interactions/NumberTicker';
import { useEffect, useState } from 'react';
import { Text, View } from 'react-native';
import { router } from 'expo-router';
import { apiRequest } from '../api/client';
import { useAuthStore } from '../store/authStore';
import { Card, Disclosure, Field, Button, Chip, Notice, ui } from './CommunityUI';

import { IconButton, ListItem, OverflowMenu } from './SocialUI';
import { colors } from '../theme/colors';

export function Discussion({ id, kind }: { id: string; kind: 'event' | 'place' }) {
  useThemeRevision();
  const token = useAuthStore(s => s.token);
  const userId = useAuthStore(s => s.user?.id);
  const reviewQuery = useQuery({ queryKey: ['reviews', kind, id], queryFn: () => getReviews(kind, id), enabled: !!token });
  const summary = useQuery({ queryKey: ['review-summary', kind, id], queryFn: () => getReviewSummary(kind, id), enabled: !!token });
  const reviews = reviewQuery.data ?? [];
  const [comments, setComments] = useState<any[]>([]);
  const [body, setBody] = useState('');
  const [comment, setComment] = useState('');
  const [ratings, setRatings] = useState<Record<string, number>>({});
  const [reason, setReason] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState<{ type: string; id: string } | null>(null);
  const dimensions = kind === 'event' ? ['worth_attending', 'crowd', 'value', 'accessibility', 'would_attend_again'] : ['atmosphere', 'price', 'accessibility', 'cleanliness', 'crowdedness', 'family_friendliness', 'solo_friendliness'];
  async function load() {
    try { await reviewQuery.refetch(); await summary.refetch(); if (kind === 'event') setComments(await apiRequest<any[]>(`/community/events/${id}/comments`, { auth: true })); }
    catch (e: any) { setNotice(e.message); }
  }
  useEffect(() => { if (token) void load(); }, [id, token]);
  async function act(path: string, payload?: unknown) {
    if (busy) return; setBusy(true); setNotice('');
    try { await apiRequest(path, { method: 'POST', auth: true, body: payload }); await load(); setNotice('Saved.'); }
    catch (e: any) { setNotice(e.message); } finally { setBusy(false); }
  }
  if (!token) return <Card><Text style={ui.text}>Sign in to read reviews and join the discussion.</Text><Button title="Sign in" onPress={() => router.push({ pathname: '/auth', params: { mode: 'login' } })} /></Card>;
  return <View style={{ gap: 16, padding: 20 }}><Notice text={notice} />
    <Text style={ui.heading}>Community reviews</Text>
    {summary.data && <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}><NumberTicker value={summary.data.count} label="public reviews" /><Text style={ui.muted}>public reviews</Text></View>}
    {summary.data?.dimensions[kind === 'event' ? 'worth_attending' : 'atmosphere'] && <StarRating label={kind === 'event' ? 'Worth attending' : 'Atmosphere'} value={summary.data.dimensions[kind === 'event' ? 'worth_attending' : 'atmosphere'].average} />}
    {(reviewQuery.isPending || summary.isPending) && <Text style={ui.muted}>Loading reviews…</Text>}
    {(reviewQuery.isError || summary.isError) && <><Notice text={reviewQuery.error?.message ?? summary.error?.message} /><Button variant="secondary" title="Retry reviews" onPress={load} /></>}
    {!reviewQuery.isPending && !reviewQuery.isError && reviews.length === 0 && <Text style={ui.muted}>Be the first to share your experience.</Text>}
    {reviews.map(review => <View key={review.id} style={{ paddingVertical: 16, gap: 8, borderBottomWidth: .5, borderColor: colors.border }}>
      <Text style={ui.text}>{review.body}</Text>{Object.entries(review.dimensions).map(([key, value]) => <View key={key} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}><Text style={ui.muted}>{key.replaceAll('_', ' ')}</Text><StarRating label={key.replaceAll('_', ' ')} value={value} /></View>)}
      <Text style={ui.muted}>{review.attendance_verified ? 'Attendance verified' : 'Attendance not verified'} · {review.helpful} found this helpful</Text>
      <View style={ui.row}><IconButton icon="thumbs-up-outline" label="Mark review helpful" onPress={() => { if (!busy) void act(`/community/reviews/${review.id}/helpful`); }} /><IconButton icon="person-outline" label="View review contributor" onPress={() => router.push(`/member/${review.user_id}`)} /><IconButton icon="flag-outline" label="Report review" onPress={() => setReport({ type: 'review', id: review.id })} /></View>
    </View>)}
    <FeedbackComposer key={`${kind}/${id}`} id={id} kind={kind} ownReview={reviews.find(review => review.user_id === userId)} />
    {kind === 'event' && <Disclosure title="Conversation" icon="chatbubbles-outline" initiallyOpen>
      {comments.map(item => <View key={item.id} style={{ gap: 8, paddingVertical: 12 }}><Text style={ui.text}>{item.body}</Text><View style={ui.row}><IconButton icon="person-outline" label="View comment contributor" onPress={() => router.push(`/member/${item.user_id}`)} /><IconButton icon="flag-outline" label="Report comment" onPress={() => setReport({ type: 'comment', id: item.id })} /></View></View>)}
      <Field label="Add a comment" value={comment} onChange={setComment} multiline /><Button title="Post comment" busy={busy} onPress={() => act(`/community/events/${id}/comments`, { body: comment })} />
    </Disclosure>}
    <Disclosure title="More actions" icon="ellipsis-horizontal">
      <ListItem icon="create-outline" title="Suggest a correction" onPress={() => router.push({ pathname: "/correction", params: { type: kind, id } })} />
      <ListItem icon="albums-outline" title="Create a collection with this item" onPress={() => router.push({ pathname: "/collection", params: { type: kind, id } })} />
      <ListItem icon="flag-outline" title={'Report this ' + kind} onPress={() => setReport({ type: kind, id })} />
      <Button variant="secondary" title="Refresh discussion" onPress={load} />
    </Disclosure>
    <OverflowMenu visible={!!report} title="Report to moderation" onClose={() => setReport(null)}>
      <Text style={ui.text}>Explain what needs review. Your report is not shown publicly.</Text><Field label="Report reason" value={reason} onChange={setReason} multiline />
      <Button title="Submit report" busy={busy} onPress={() => { if (report) void act('/community/reports', { target_type: report.type, target_id: report.id, reason }); }} />
      <Notice text={notice} />
    </OverflowMenu>
  </View>;
}
