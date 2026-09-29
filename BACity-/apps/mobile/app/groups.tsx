import { useMemo, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { groupsApi, GroupSummary } from "../src/api/groups";
import { Button, Chip, Field } from "../src/components/CommunityUI";
import { EmptyState } from "../src/components/EmptyState";
import { ScreenHeader } from "../src/components/SocialUI";
import { groupRoute, groupStateLabel, resolveGroupsView } from "../src/groups/presentation";
import { useGroupMutation, useGroups } from "../src/hooks/useGroups";
import { PlusGateAction } from "../src/plus/usePlusGate";
import { useAuthStore } from "../src/store/authStore";
import { colors } from "../src/theme/colors";
import { fonts } from "../src/theme/fonts";
import type { EventCategory } from "../src/types/event";
import { defaultWeekendStart } from "../src/weekend/presentation";

const CATEGORIES: EventCategory[] = ["Music", "Culture", "Arts", "Nightlife", "Theatre", "Family", "Community", "Food & Drink"];

function GroupRow({ item }: { item: GroupSummary }) {
  return <Pressable onPress={() => router.push(groupRoute(item.id))} style={({ pressed }) => [styles.groupRow, pressed && styles.pressed]}>
    <View style={styles.groupIcon}><Ionicons name="people" size={20} color={colors.primaryDark} /></View>
    <View style={styles.groupCopy}><Text style={styles.groupName} numberOfLines={1}>{item.name}</Text><Text style={styles.groupMeta}>{groupStateLabel(item.status)} · {item.participant_count}/{item.max_participants} people</Text></View>
    <Ionicons name="chevron-forward" size={18} color={colors.textMuted} />
  </Pressable>;
}

export default function GroupsScreen() {
  const token = useAuthStore(state => state.token);
  const query = useGroups(!!token);
  const createMutation = useGroupMutation();
  const joinMutation = useGroupMutation();
  const [name, setName] = useState("Weekend crew");
  const [date, setDate] = useState(() => defaultWeekendStart());
  const [startTime, setStartTime] = useState("18:00");
  const [endTime, setEndTime] = useState("23:00");
  const [categories, setCategories] = useState<EventCategory[]>([]);
  const [joinCode, setJoinCode] = useState("");
  const [createdCode, setCreatedCode] = useState<string | null>(null);
  const [createdGroup, setCreatedGroup] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const groups = query.data ?? [];
  const hosted = useMemo(() => groups.filter(group => group.role === "host"), [groups]);
  const participating = useMemo(() => groups.filter(group => group.role === "participant"), [groups]);
  const state = resolveGroupsView(!!token, query.isPending, query.isError, groups.length);

  function toggle(category: EventCategory) {
    setCategories(current => current.includes(category) ? current.filter(item => item !== category) : current.length < 6 ? [...current, category] : current);
  }

  async function create() {
    setNotice(null);
    try {
      const result = await createMutation.mutateAsync(() => groupsApi.create({ name, target_date: date, start_time: startTime, end_time: endTime, categories, max_participants: 8 }));
      const created = result as Awaited<ReturnType<typeof groupsApi.create>>;
      setCreatedCode(created.join_code); setCreatedGroup(created.group.id);
    } catch (error) { setNotice((error as Error).message); }
  }

  async function join() {
    setNotice(null);
    try {
      const group = await joinMutation.mutateAsync(() => groupsApi.join(joinCode)) as Awaited<ReturnType<typeof groupsApi.join>>;
      setJoinCode(""); router.push(groupRoute(group.id));
    } catch (error) { setNotice((error as Error).message); }
  }

  if (state === "signed_out") return <SafeAreaView style={styles.safe}><ScreenHeader title="Groups" /><EmptyState title="Sign in to join a group" subtitle="Only the person creating Group Match needs BACity+." action="Sign in" onAction={() => router.push({ pathname: "/auth", params: { mode: "login" } })} /></SafeAreaView>;
  if (state === "loading") return <SafeAreaView style={styles.safe}><ScreenHeader title="Groups" /><View style={styles.center}><ActivityIndicator color={colors.primary} /></View></SafeAreaView>;

  return <SafeAreaView style={styles.safe} edges={["top", "bottom"]}><ScreenHeader title="Groups" /><ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
    <Text style={styles.heading}>Decide together</Text><Text style={styles.subtitle}>Create with BACity+, or join and vote for free when a host invites you.</Text>
    <View style={styles.card}><Text style={styles.cardTitle}>Create a group</Text><Field label="Group name" value={name} onChange={setName} /><Field label="Date (YYYY-MM-DD)" value={date} onChange={setDate} /><View style={styles.split}><View style={styles.flex}><Field label="Start" value={startTime} onChange={setStartTime} /></View><View style={styles.flex}><Field label="End" value={endTime} onChange={setEndTime} /></View></View><View style={styles.chips}>{CATEGORIES.map(category => <Chip key={category} title={category} active={categories.includes(category)} onPress={() => toggle(category)} />)}</View>
      <PlusGateAction feature="group_match" onAllowed={create}>{({ onPress, loading }) => <Button title="Create with BACity+" busy={loading || createMutation.isPending} onPress={onPress} />}</PlusGateAction>
      {createdCode ? <View style={styles.codeBox}><Text style={styles.codeLabel}>PRIVATE JOIN CODE · SHARE DIRECTLY</Text><Text selectable style={styles.code}>{createdCode}</Text>{createdGroup ? <Text style={styles.link} onPress={() => router.push(groupRoute(createdGroup))}>Open group</Text> : null}</View> : null}
    </View>
    <View style={styles.card}><Text style={styles.cardTitle}>Join an invited group</Text><Text style={styles.helper}>Joining, preferences, voting and results do not require BACity+.</Text><Field label="Join code" value={joinCode} onChange={setJoinCode} /><Button title="Join group" busy={joinMutation.isPending} onPress={join} /></View>
    {notice ? <Text accessibilityRole="alert" style={styles.error}>{notice}</Text> : null}
    {state === "error" ? <EmptyState title="Groups couldn't load" action="Try again" onAction={() => void query.refetch()} /> : null}
    {hosted.length ? <><Text style={styles.section}>HOSTED BY YOU</Text>{hosted.map(group => <GroupRow key={group.id} item={group} />)}</> : null}
    {participating.length ? <><Text style={styles.section}>PARTICIPATING</Text>{participating.map(group => <GroupRow key={group.id} item={group} />)}</> : null}
    {state === "empty" ? <EmptyState title="No group sessions yet" subtitle="Create one with BACity+ or enter a private invite code." /> : null}
  </ScrollView></SafeAreaView>;
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background }, center: { flex: 1, alignItems: "center", justifyContent: "center" }, content: { paddingHorizontal: 18, paddingBottom: 40 }, heading: { color: colors.text, fontFamily: fonts.black, fontSize: 28, marginTop: 10 }, subtitle: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 12, lineHeight: 18, marginTop: 6 },
  card: { marginTop: 18, padding: 15, borderRadius: 22, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, gap: 11 }, cardTitle: { color: colors.text, fontFamily: fonts.black, fontSize: 17 }, helper: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 10, lineHeight: 15 }, split: { flexDirection: "row", gap: 9 }, flex: { flex: 1 }, chips: { flexDirection: "row", flexWrap: "wrap", gap: 7 },
  codeBox: { padding: 11, borderRadius: 15, backgroundColor: colors.primarySoft }, codeLabel: { color: colors.textMuted, fontFamily: fonts.semibold, fontSize: 8 }, code: { color: colors.text, fontFamily: fonts.medium, fontSize: 10, marginTop: 6 }, link: { color: colors.primaryDark, fontFamily: fonts.semibold, fontSize: 11, marginTop: 9 }, error: { color: colors.danger, fontFamily: fonts.medium, fontSize: 11, marginTop: 12 },
  section: { color: colors.textMuted, fontFamily: fonts.black, fontSize: 9, letterSpacing: 1.2, marginTop: 24, marginBottom: 8 }, groupRow: { minHeight: 72, padding: 12, borderRadius: 19, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, flexDirection: "row", alignItems: "center", gap: 11, marginBottom: 8 }, pressed: { opacity: .7 }, groupIcon: { width: 42, height: 42, borderRadius: 15, backgroundColor: colors.primarySoft, alignItems: "center", justifyContent: "center" }, groupCopy: { flex: 1 }, groupName: { color: colors.text, fontFamily: fonts.black, fontSize: 14 }, groupMeta: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 10, marginTop: 4 },
});
