import { usePullRefresh } from "../src/hooks/usePullRefresh";
import { useRef, useState } from 'react';
import { FlatList, Text, View } from 'react-native';
import { SafeAreaView } from '../src/components/navigation/ContentSafeArea';
import { router, type Href } from 'expo-router';
import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query';
import { getNotifications, markNotificationRead, type Notification } from '../src/api/community';
import { notificationRoute } from '../src/interactions/policy';
import { ScreenHeader, SkeletonList } from '../src/components/SocialUI';
import { MorphActionButton } from '../src/components/interactions/ActionButton';
import { EmptyState } from '../src/components/EmptyState';
import { AnimatedPressable } from '../src/components/motion/Motion';
import { AppIcon } from '../src/components/AppIcon';
import { useAuthStore } from '../src/store/authStore';
import { colors } from '../src/theme/colors';
import { tokens } from '../src/theme/tokens';
import { useThemeRevision } from '../src/theme/appearance';
export default function NotificationsScreen() {
  const pullRefresh = usePullRefresh(() => query.refetch());
  useThemeRevision();
  const token = useAuthStore(state => state.token); const client = useQueryClient();
  const [error, setError] = useState(''); const opening = useRef(new Set<string>());
  const query = useInfiniteQuery({ queryKey: ['notification-inbox'], initialPageParam: 0, queryFn: ({ pageParam }) => getNotifications(pageParam, 30), getNextPageParam: (last, pages) => last.length === 30 ? pages.flat().length : undefined, enabled: !!token });
  async function open(item: Notification) {
    if (opening.current.has(item.id)) return;
    opening.current.add(item.id); setError('');
    try {
      if (!item.read_at) {
        await markNotificationRead(item.id);
        await Promise.all([client.invalidateQueries({ queryKey: ['notification-inbox'] }), client.invalidateQueries({ queryKey: ['notification-summary'] }), client.invalidateQueries({ queryKey: ['notifications'] })]);
      }
      const destination = notificationRoute(item.kind, item.target_id);
      if (destination) router.push(destination as Href);
      else setError('Marked as read. This update has no available destination.');
    } catch (failure: any) { setError(failure.message ?? 'Could not open this update. Tap it to retry.'); }
    finally { opening.current.delete(item.id); }
  }
  return <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }} edges={['top', 'bottom']}><ScreenHeader title="Notifications" />
    {!!error && <Text accessibilityRole="alert" style={{ ...tokens.type.metadata, color: colors.danger, padding: 16 }}>{error}</Text>}
    {!token ? <EmptyState title="Sign in to see notifications" subtitle="Your updates stay in your account." action="Sign in" onAction={() => router.push('/auth')} /> : query.isPending ? <View style={{ padding: 20 }}><SkeletonList /></View> : query.isError && !query.data ? <EmptyState title="Notifications couldn't load" subtitle={query.error.message} action="Try again" onAction={() => void query.refetch()} /> : <FlatList
      data={query.data?.pages.flat()} keyExtractor={item => item.id} contentContainerStyle={{ width: '100%', maxWidth: 760, alignSelf: 'center', paddingHorizontal: 20, paddingBottom: 32, flexGrow: 1 }} refreshing={pullRefresh.refreshing} onRefresh={pullRefresh.onRefresh}
      ListEmptyComponent={<EmptyState title="You're all caught up" subtitle="New community activity will appear here." />}
      renderItem={({ item }) => <AnimatedPressable accessibilityRole="button" accessibilityLabel={`${item.read_at ? 'Read' : 'Unread'} notification. ${item.body}`} onPress={() => void open(item)} style={{ minHeight: 80, padding: 12, borderRadius: 16, marginBottom: 8, flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: item.read_at ? 'transparent' : colors.primarySoft }}>
        <AppIcon name={item.kind === 'message' ? 'chatbubble-outline' : 'notifications-outline'} size={24} color={colors.primaryDark} /><View style={{ flex: 1, gap: 4 }}><Text style={{ ...tokens.type.body, color: colors.text }}>{item.body}</Text><Text style={{ ...tokens.type.caption, color: colors.textMuted }}>{!item.read_at ? 'Unread · ' : ''}{new Date(item.created_at).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</Text></View><AppIcon name="chevron-forward" size={18} color={colors.textMuted} />
      </AnimatedPressable>}
      ListFooterComponent={query.hasNextPage ? <MorphActionButton title="Load more" variant="secondary" state={query.isFetchingNextPage ? 'loading' : query.isFetchNextPageError ? 'error' : 'idle'} onPress={() => void query.fetchNextPage()} /> : null}
    />}
  </SafeAreaView>;
}
