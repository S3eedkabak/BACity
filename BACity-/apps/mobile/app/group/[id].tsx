import { useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router, useLocalSearchParams } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { groupsApi, GroupCandidate, VoteValue } from "../../src/api/groups";
import { Button, Chip } from "../../src/components/CommunityUI";
import { EmptyState } from "../../src/components/EmptyState";
import { ScreenHeader } from "../../src/components/SocialUI";
import { groupEventRoute, groupStateLabel } from "../../src/groups/presentation";
import { useGroup, useGroupMutation } from "../../src/hooks/useGroups";
import { PlusGateAction } from "../../src/plus/usePlusGate";
import { useRecommendationLocation } from "../../src/recommendations/useRecommendationLocation";
import { useAuthStore } from "../../src/store/authStore";
import { colors } from "../../src/theme/colors";
import { fonts } from "../../src/theme/fonts";
import type { EventCategory } from "../../src/types/event";

const CATEGORIES: EventCategory[] = ["Music", "Culture", "Arts", "Nightlife", "Theatre", "Family", "Community", "Food & Drink"];

function CandidateCard({ candidate, voting, busy, onVote }: { candidate: GroupCandidate; voting: boolean; busy: boolean; onVote: (value: VoteValue) => void }) {
  return <View style={styles.candidate}>
    <Pressable onPress={() => router.push(groupEventRoute(candidate.event.id))} style={({ pressed }) => [styles.eventTop, pressed && styles.pressed]}>
      <View style={styles.eventCopy}><Text style={styles.eventTime}>{new Date(candidate.event.start_time).toLocaleString(undefined, { weekday: "short", hour: "2-digit", minute: "2-digit" })}</Text><Text style={styles.eventTitle}>{candidate.event.title}</Text><Text style={styles.eventVenue}>{candidate.event.venue?.name ?? candidate.event.address ?? "Bratislava"}</Text></View><Ionicons name="chevron-forward" size={18} color={colors.textMuted} />
    </Pressable>
    {candidate.explanations[0] ? <Text style={styles.reason}>{candidate.explanations[0]}</Text> : null}
    {voting ? <View style={styles.votes}>{([[-1, "Dislike", "thumbs-down-outline"], [0, "Skip", "remove-outline"], [1, "Like", "thumbs-up-outline"]] as const).map(([value, label, icon]) => <Pressable key={value} disabled={busy} onPress={() => onVote(value)} style={[styles.vote, candidate.my_vote === value && styles.voteActive]}><Ionicons name={icon} size={16} color={candidate.my_vote === value ? colors.white : colors.primaryDark} /><Text style={[styles.voteText, candidate.my_vote === value && styles.voteTextActive]}>{label}</Text></Pressable>)}</View> : candidate.aggregate ? <Text style={styles.aggregate}>{candidate.aggregate.likes} likes · {candidate.aggregate.neutral} neutral · {candidate.aggregate.dislikes} dislikes</Text> : null}
  </View>;
}

export default function GroupDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const token = useAuthStore(state => state.token);
  const query = useGroup(id ?? "", !!token);
  const mutation = useGroupMutation(id);
  const group = query.data;
  const [liked, setLiked] = useState<EventCategory[]>([]);
  const [disliked, setDisliked] = useState<EventCategory[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [inviteCode, setInviteCode] = useState<string | null>(null);
  const location = useRecommendationLocation(group?.role === "host");

  async function run(work: () => Promise<unknown>, success?: string) {
    setNotice(null);
    try { await mutation.mutateAsync(work); if (success) setNotice(success); }
    catch (error) { setNotice((error as Error).message); }
  }
  function preference(category: EventCategory, kind: "like" | "dislike") {
    if (kind === "like") { setLiked(current => current.includes(category) ? current.filter(item => item !== category) : current.length < 6 ? [...current, category] : current); setDisliked(current => current.filter(item => item !== category)); }
    else { setDisliked(current => current.includes(category) ? current.filter(item => item !== category) : current.length < 6 ? [...current, category] : current); setLiked(current => current.filter(item => item !== category)); }
  }

  if (!token) return <SafeAreaView style={styles.safe}><ScreenHeader title="Group" /><EmptyState title="Sign in to open this private group" action="Sign in" onAction={() => router.push({ pathname: "/auth", params: { mode: "login" } })} /></SafeAreaView>;
  if (query.isPending) return <SafeAreaView style={styles.safe}><ScreenHeader title="Group" /><View style={styles.center}><ActivityIndicator color={colors.primary} /></View></SafeAreaView>;
  if (query.isError || !group) return <SafeAreaView style={styles.safe}><ScreenHeader title="Group" /><EmptyState title="Group unavailable" subtitle="The invite may be private, removed, or expired." action="Try again" onAction={() => void query.refetch()} /></SafeAreaView>;
  const locked = ["voting", "expired", "cancelled"].includes(group.status);
  const voting = group.round?.status === "voting";

  return <SafeAreaView style={styles.safe} edges={["top", "bottom"]}><ScreenHeader title={group.name} /><ScrollView contentContainerStyle={styles.content}>
    <View style={styles.statusRow}><Text style={styles.status}>{groupStateLabel(group.status)}</Text><Text style={styles.role}>{group.role === "host" ? "HOSTED BY YOU" : "PARTICIPATING"}</Text></View>
    <Text style={styles.date}>{new Date(group.starts_at).toLocaleString(undefined, { weekday: "long", month: "long", day: "numeric", hour: "2-digit", minute: "2-digit" })}</Text>
    <View style={styles.people}><Text style={styles.section}>PEOPLE · {group.participant_count}/{group.max_participants}</Text>{group.participants.map(person => <View key={person.id} style={styles.person}><View style={styles.avatar}><Text style={styles.avatarText}>{person.display_name.slice(0, 1).toUpperCase()}</Text></View><Text style={styles.personName}>{person.display_name}{person.is_host ? " · Host" : ""}</Text><Text style={person.ready ? styles.ready : styles.waiting}>{person.ready ? "Ready" : "Waiting"}</Text></View>)}</View>

    {!locked && !group.round ? <View style={styles.panel}><Text style={styles.panelTitle}>Your session preferences</Text><Text style={styles.helper}>Private to BACity's matching service. Other participants do not see these choices.</Text><Text style={styles.label}>LIKE</Text><View style={styles.chips}>{CATEGORIES.map(category => <Chip key={`l-${category}`} title={category} active={liked.includes(category)} onPress={() => preference(category, "like")} />)}</View><Text style={styles.label}>DISLIKE</Text><View style={styles.chips}>{CATEGORIES.map(category => <Chip key={`d-${category}`} title={category} active={disliked.includes(category)} onPress={() => preference(category, "dislike")} />)}</View><Button title="Save and mark ready" busy={mutation.isPending} onPress={() => run(() => groupsApi.preferences(group.id, liked, disliked), "Preferences saved privately.")} /></View> : null}

    {group.role === "host" && ["open", "ready"].includes(group.status) ? <View style={styles.panel}><Text style={styles.panelTitle}>Invite privately</Text><Text style={styles.helper}>Generate a high-entropy code and share it directly with BACity members.</Text><Button title="Generate join code" busy={mutation.isPending} onPress={() => run(async () => { const invite = await groupsApi.invite(group.id); setInviteCode(invite.join_code); })} />{inviteCode ? <Text selectable style={styles.code}>{inviteCode}</Text> : null}</View> : null}

    {group.role === "host" && ["ready", "completed"].includes(group.status) ? <View style={styles.panel}><Text style={styles.panelTitle}>{group.round ? "Generate a new match" : "Generate Group Match"}</Text><Text style={styles.helper}>{location.coordinates ? "Using one approximate host-selected planning location." : "Citywide matching works without location."}</Text><View style={styles.inline}><Pressable onPress={() => void (location.enabled ? location.disable() : location.enable())}><Text style={styles.link}>{location.enabled ? "Turn location off" : "Use approximate location"}</Text></Pressable></View><PlusGateAction feature="group_match" onAllowed={() => run(() => groupsApi.generate(group.id, location.coordinates))}>{({ onPress, loading }) => <Button title="Generate Group Match" busy={loading || mutation.isPending} onPress={onPress} />}</PlusGateAction></View> : null}

    {group.round ? <View style={styles.round}><View style={styles.roundHeader}><Text style={styles.panelTitle}>{voting ? "Vote independently" : "Group result"}</Text><Text style={styles.progress}>{group.round.voted_participants}/{group.round.participant_count} complete</Text></View>{!group.round.candidates.length ? <EmptyState title="No suitable events found" subtitle="BACity did not fabricate candidates for this session." /> : group.round.candidates.map(candidate => <CandidateCard key={candidate.id} candidate={candidate} voting={voting} busy={mutation.isPending} onVote={value => run(() => groupsApi.vote(group.id, group.round!.id, candidate.id, value))} />)}{voting && group.role === "host" ? <Button title="Close voting and reveal" busy={mutation.isPending} onPress={() => run(() => groupsApi.reveal(group.id, group.round!.id))} /> : null}</View> : null}

    {group.status === "expired" ? <EmptyState title="This session expired" subtitle="Existing results remain readable until the retention window ends, but the session is no longer writable." /> : null}
    {group.status === "cancelled" ? <EmptyState title="This session was cancelled" /> : null}
    {notice ? <Text accessibilityRole="alert" style={styles.notice}>{notice}</Text> : null}
    <View style={styles.bottomActions}>{group.role === "host" && !["cancelled", "expired"].includes(group.status) ? <Pressable onPress={() => run(() => groupsApi.cancel(group.id))}><Text style={styles.danger}>Cancel group</Text></Pressable> : group.role === "participant" && !["cancelled", "expired"].includes(group.status) ? <Pressable onPress={() => run(async () => { await groupsApi.leave(group.id); router.replace("/groups"); })}><Text style={styles.danger}>Leave group</Text></Pressable> : null}</View>
  </ScrollView></SafeAreaView>;
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background }, center: { flex: 1, alignItems: "center", justifyContent: "center" }, content: { paddingHorizontal: 18, paddingBottom: 40 }, statusRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: 10 }, status: { color: colors.primaryDark, fontFamily: fonts.black, fontSize: 12 }, role: { color: colors.textMuted, fontFamily: fonts.semibold, fontSize: 8, letterSpacing: 1 }, date: { color: colors.text, fontFamily: fonts.black, fontSize: 21, marginTop: 8 }, section: { color: colors.textMuted, fontFamily: fonts.black, fontSize: 9, letterSpacing: 1.1, marginBottom: 8 },
  people: { marginTop: 20 }, person: { minHeight: 48, flexDirection: "row", alignItems: "center", gap: 9, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: colors.border }, avatar: { width: 32, height: 32, borderRadius: 12, backgroundColor: colors.primarySoft, alignItems: "center", justifyContent: "center" }, avatarText: { color: colors.primaryDark, fontFamily: fonts.black }, personName: { flex: 1, color: colors.text, fontFamily: fonts.semibold, fontSize: 11 }, ready: { color: colors.primaryDark, fontFamily: fonts.semibold, fontSize: 9 }, waiting: { color: colors.textMuted, fontFamily: fonts.medium, fontSize: 9 },
  panel: { marginTop: 18, padding: 15, borderRadius: 22, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, gap: 11 }, panelTitle: { color: colors.text, fontFamily: fonts.black, fontSize: 17 }, helper: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 10, lineHeight: 15 }, label: { color: colors.textMuted, fontFamily: fonts.black, fontSize: 8, letterSpacing: 1 }, chips: { flexDirection: "row", flexWrap: "wrap", gap: 7 }, code: { color: colors.text, backgroundColor: colors.primarySoft, borderRadius: 12, padding: 10, fontFamily: fonts.medium, fontSize: 9 }, inline: { flexDirection: "row" }, link: { color: colors.primaryDark, fontFamily: fonts.semibold, fontSize: 10, paddingVertical: 6 },
  round: { marginTop: 22, gap: 10 }, roundHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" }, progress: { color: colors.textMuted, fontFamily: fonts.medium, fontSize: 10 }, candidate: { padding: 14, borderRadius: 21, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border }, eventTop: { flexDirection: "row", alignItems: "center" }, pressed: { opacity: .7 }, eventCopy: { flex: 1 }, eventTime: { color: colors.primaryDark, fontFamily: fonts.semibold, fontSize: 9 }, eventTitle: { color: colors.text, fontFamily: fonts.black, fontSize: 15, marginTop: 4 }, eventVenue: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 10, marginTop: 4 }, reason: { color: colors.primaryDark, fontFamily: fonts.medium, fontSize: 9, marginTop: 9 },
  votes: { flexDirection: "row", gap: 7, marginTop: 12 }, vote: { flex: 1, minHeight: 38, borderRadius: 13, backgroundColor: colors.primarySoft, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 5 }, voteActive: { backgroundColor: colors.primary }, voteText: { color: colors.primaryDark, fontFamily: fonts.semibold, fontSize: 9 }, voteTextActive: { color: colors.white }, aggregate: { color: colors.textMuted, fontFamily: fonts.semibold, fontSize: 10, marginTop: 10 }, notice: { color: colors.primaryDark, fontFamily: fonts.medium, fontSize: 10, marginTop: 14 }, bottomActions: { alignItems: "center", marginTop: 24 }, danger: { color: colors.danger, fontFamily: fonts.semibold, fontSize: 11, padding: 12 },
});
