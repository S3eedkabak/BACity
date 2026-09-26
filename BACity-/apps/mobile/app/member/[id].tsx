import { useAuthStore } from "../../src/store/authStore";
import { Ionicons } from "@expo/vector-icons";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import { Image, Pressable, StyleSheet, Text, View } from "react-native";
import { apiRequest } from "../../src/api/client";
import {
  Page,
  Card,
  Field,
  Button,
  Chip,
  Notice,
  ui,
} from "../../src/components/CommunityUI";
import { colors } from "../../src/theme/colors";
import { fonts } from "../../src/theme/fonts";

export default function Member() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const user = useAuthStore(s => s.user);
  const [role, setRole] = useState("USER");
  const [profile, setProfile] = useState<any>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [body, setBody] = useState("");
  const [reason, setReason] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [historyType, setHistoryType] = useState<"contributions" | "reviews" | "followers" | "following">("contributions");
  const [history, setHistory] = useState<any[]>([]);
  const [historyMore, setHistoryMore] = useState(false);

  const initials = useMemo(() => {
    const source = profile?.display_name || profile?.email || "BA";
    return source
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part: string) => part[0]?.toUpperCase())
      .join("");
  }, [profile]);

  async function load() {
    try {
      setProfile(await apiRequest(`/community/profiles/${id}`, { auth: true }));
      setMessages(
        await apiRequest<any[]>(`/community/messages/${id}`, { auth: true })
      );
    } catch (e: any) {
      setNotice(e.message);
    }
  }

  useEffect(() => {
    void load();
  }, [id]);

  async function loadHistory(more = false) {
    try {
      const result = await apiRequest<any[]>(`/community/profiles/${id}/${historyType}`, { auth: true, params: { offset: more ? history.length : 0, limit: 10 } });
      setHistory(current => more ? [...current, ...result] : result);
      setHistoryMore(result.length === 10);
    } catch (e: any) { setNotice(e.message); }
  }

  useEffect(() => { setHistory([]); void loadHistory(false); }, [id, historyType]);

  async function act(path: string, payload?: unknown) {
    setBusy(true);
    setNotice("");
    try {
      await apiRequest(path, { method: "POST", auth: true, body: payload });
      setBody("");
      await load();
      setNotice("Saved.");
    } catch (e: any) {
      setNotice(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function toggleFollow() {
    setBusy(true); setNotice("");
    try {
      if (profile?.follow_id) await apiRequest(`/community/follows/${profile.follow_id}`, { method: "DELETE", auth: true });
      else await apiRequest('/community/follows', { method: 'POST', auth: true, body: { target_type: profile?.role === 'GUIDE' ? 'guide' : 'user', target_id: id } });
      await load(); setNotice(profile?.follow_id ? 'Unfollowed.' : 'Following.');
    } catch (e: any) { setNotice(e.message); } finally { setBusy(false); }
  }

  return (
    <Page title="Community profile">
      <Notice text={notice} />
      {user?.role === 'ADMIN' && user.id !== id && <Card><Text style={ui.heading}>Member role</Text><View style={ui.row}>{['USER', 'GUIDE', 'ORGANIZER', 'MODERATOR', 'ADMIN'].map(value => <Button key={value} title={(role === value ? '✓ ' : '') + value} onPress={() => setRole(value)} />)}</View><Field label="Reason for role change" value={reason} onChange={setReason} /><Button title="Apply selected role" busy={busy} onPress={async () => { setBusy(true); try { await apiRequest(`/community/moderation/users/${id}/role`, { method: 'PATCH', auth: true, body: { role, reason } }); await load(); setNotice('Role updated.'); } catch (e: any) { setNotice(e.message); } finally { setBusy(false); } }} /></Card>}


      {profile && (
        <>
          <View style={styles.hero}>
            <View style={styles.avatarWrap}>
              {profile.avatar_url ? (
                <Image source={{ uri: profile.avatar_url }} style={styles.avatar} />
              ) : (
                <View style={styles.avatarFallback}>
                  <Text style={styles.avatarText}>{initials}</Text>
                </View>
              )}
              {!!profile.identity_verified && (
                <View style={styles.verified}>
                  <Ionicons name="checkmark" size={13} color={colors.white} />
                </View>
              )}
            </View>

            <Text style={styles.name}>
              {profile.display_name ?? "BACity member"}
            </Text>

            <View style={styles.badges}>
              <View style={styles.badge}>
                <Ionicons name="location-outline" size={12} color={colors.primaryDark} />
                <Text style={styles.badgeText}>
                  {profile.neighborhood || profile.city || "Bratislava"}
                </Text>
              </View>
              {!!profile.reputation_level && (
                <View style={styles.badge}>
                  <Ionicons name="sparkles-outline" size={12} color={colors.primaryDark} />
                  <Text style={styles.badgeText}>{profile.reputation_level}</Text>
                </View>
              )}
            </View>

            {!!profile.bio && <Text style={styles.bio}>{profile.bio}</Text>}

            <View style={styles.stats}>
              <View style={styles.stat}>
                <Text style={styles.statValue}>{profile.followers ?? 0}</Text>
                <Text style={styles.statLabel}>Followers</Text>
              </View>
              <View style={styles.divider} />
              <View style={styles.stat}>
                <Text style={styles.statValue}>{profile.following ?? 0}</Text>
                <Text style={styles.statLabel}>Following</Text>
              </View>
              <View style={styles.divider} />
              <View style={styles.stat}>
                <Text style={styles.statValue}>{profile.reputation ?? 0}</Text>
                <Text style={styles.statLabel}>Reputation</Text>
              </View>
            </View>

            {user?.id !== id && <Pressable
              style={({ pressed }) => [
                styles.follow,
                pressed && styles.pressed,
              ]}
              disabled={busy}
              onPress={toggleFollow}
            >
              <Ionicons name={profile.is_following ? "checkmark-circle-outline" : "person-add-outline"} size={17} color={colors.white} />
              <Text style={styles.followText}>{profile.is_following ? "Following · tap to unfollow" : "Follow"}</Text>
            </Pressable>}
          </View>

          <Card>
            <View style={styles.sectionTitleRow}><View style={styles.sectionIcon}><Ionicons name="ribbon-outline" size={19} color={colors.primaryDark} /></View><View style={styles.sectionCopy}><Text style={styles.sectionTitle}>Community activity</Text><Text style={styles.sectionSubtitle}>{profile.contributions_count ?? 0} published contributions · {profile.reviews_count ?? 0} reviews</Text></View></View>
            <View style={ui.row}>{(["contributions", "reviews", "followers", "following"] as const).map(value => <Chip key={value} title={value} active={historyType === value} onPress={() => setHistoryType(value)} />)}</View>
            {!history.length && <Text style={ui.muted}>Nothing public here yet.</Text>}
            {history.map(item => <View key={item.id} style={styles.historyItem}>
              <Text style={ui.heading}>{item.title ?? item.target_name ?? item.display_name ?? item.target_label ?? 'Activity'}</Text>
              <Text style={ui.muted}>{item.kind ?? item.target_type ?? item.reputation_level}{item.created_at || item.updated_at ? ` · ${new Date(item.created_at ?? item.updated_at).toLocaleDateString()}` : ''}</Text>
              {item.body && <Text style={ui.text}>{item.body}</Text>}
              {historyType === 'followers' && <Button title="View profile" onPress={() => router.push(`/member/${item.id}`)} />}
              {historyType === 'following' && ['user', 'guide'].includes(item.target_type) && <Button title="View profile" onPress={() => router.push(`/member/${item.target_id}`)} />}
              {historyType === 'contributions' && item.published_id && <Button title="Open contribution" onPress={() => item.kind === 'event' ? router.push(`/event/${item.published_id}`) : item.kind === 'place' ? router.push(`/place/${item.published_id}`) : router.push(`/utility/${item.published_id}`)} />}
              {historyType === 'reviews' && <Button title={`Open ${item.target_type}`} onPress={() => item.target_type === 'event' ? router.push(`/event/${item.target_id}`) : router.push(`/place/${item.target_id}`)} />}
            </View>)}
            {historyMore && <Button title="Load more" onPress={() => loadHistory(true)} />}
          </Card>

          {user?.id !== id && <><Card>
            <View style={styles.sectionTitleRow}>
              <View style={styles.sectionIcon}>
                <Ionicons name="chatbubble-ellipses-outline" size={19} color={colors.primaryDark} />
              </View>
              <View style={styles.sectionCopy}>
                <Text style={styles.sectionTitle}>Conversation</Text>
                <Text style={styles.sectionSubtitle}>
                  Mutual follows can message each other. General messages depend on the recipient's settings.
                </Text>
              </View>
            </View>

            <View style={styles.thread}>
              {!messages.length && (
                <Text style={ui.muted}>No messages yet. Start the conversation.</Text>
              )}
              {messages
                .slice()
                .reverse()
                .slice(-20)
                .map((message) => {
                  const incoming = message.sender_id === id;
                  return (
                    <View
                      key={message.id}
                      style={[
                        styles.bubble,
                        incoming ? styles.bubbleIncoming : styles.bubbleMine,
                      ]}
                    >
                      <Text
                        style={[
                          styles.bubbleText,
                          !incoming && styles.bubbleTextMine,
                        ]}
                      >
                        {message.body}
                      </Text>
                    </View>
                  );
                })}
            </View>

            <Field label="Message" value={body} onChange={setBody} multiline />
            <Button
              title="Send message"
              busy={busy}
              onPress={() => act(`/community/messages/${id}`, { body })}
            />
          </Card>

          <Card>
            <View style={styles.sectionTitleRow}>
              <View style={styles.sectionIcon}>
                <Ionicons name="shield-outline" size={19} color={colors.primaryDark} />
              </View>
              <View style={styles.sectionCopy}>
                <Text style={styles.sectionTitle}>Safety controls</Text>
                <Text style={styles.sectionSubtitle}>
                  Blocking stops contact. Reports go to moderation for review.
                </Text>
              </View>
            </View>
            <Field
              label="Reason for reporting this profile"
              value={reason}
              onChange={setReason}
              multiline
            />
            <Button
              title="Report profile"
              busy={busy}
              onPress={() =>
                act("/community/reports", {
                  target_type: "user",
                  target_id: id,
                  reason,
                })
              }
            />
            <Pressable
              disabled={busy}
              onPress={() => act(`/community/blocks/${id}`)}
              style={({ pressed }) => [
                styles.blockButton,
                pressed && styles.pressed,
              ]}
            >
              <Ionicons name="ban-outline" size={17} color={colors.danger} />
              <Text style={styles.blockText}>Block this person</Text>
            </Pressable>
          </Card></>}
        </>
      )}
    </Page>
  );
}

const styles = StyleSheet.create({
  hero: {
    alignItems: "center",
    paddingTop: 12,
    paddingBottom: 8,
  },
  avatarWrap: { position: "relative" },
  avatar: {
    width: 104,
    height: 104,
    borderRadius: 38,
    backgroundColor: colors.primarySoft,
  },
  avatarFallback: {
    width: 104,
    height: 104,
    borderRadius: 38,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarText: {
    color: colors.white,
    fontFamily: fonts.black,
    fontSize: 34,
  },
  verified: {
    position: "absolute",
    right: -3,
    bottom: 5,
    width: 27,
    height: 27,
    borderRadius: 14,
    backgroundColor: colors.free,
    borderWidth: 3,
    borderColor: colors.background,
    alignItems: "center",
    justifyContent: "center",
  },
  name: {
    marginTop: 14,
    color: colors.text,
    fontFamily: fonts.black,
    fontSize: 28,
    letterSpacing: -0.8,
    textAlign: "center",
  },
  badges: {
    marginTop: 8,
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "center",
    gap: 7,
  },
  badge: {
    minHeight: 30,
    paddingHorizontal: 10,
    borderRadius: 15,
    backgroundColor: colors.primarySoft,
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
  },
  badgeText: {
    color: colors.primaryDark,
    fontFamily: fonts.semibold,
    fontSize: 9,
  },
  bio: {
    maxWidth: 315,
    marginTop: 12,
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 12,
    lineHeight: 18,
    textAlign: "center",
  },
  stats: {
    width: "100%",
    marginTop: 20,
    paddingVertical: 14,
    borderRadius: 23,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    flexDirection: "row",
    alignItems: "center",
  },
  stat: { flex: 1, alignItems: "center" },
  statValue: {
    color: colors.text,
    fontFamily: fonts.black,
    fontSize: 15,
  },
  statLabel: {
    marginTop: 2,
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 9,
  },
  divider: { width: 1, height: 28, backgroundColor: colors.border },
  follow: {
    minHeight: 50,
    marginTop: 14,
    paddingHorizontal: 24,
    borderRadius: 17,
    backgroundColor: colors.primary,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  followText: {
    color: colors.white,
    fontFamily: fonts.semibold,
    fontSize: 12,
  },
  pressed: { opacity: 0.86, transform: [{ scale: 0.985 }] },
  sectionTitleRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 11,
  },
  sectionIcon: {
    width: 42,
    height: 42,
    borderRadius: 15,
    backgroundColor: colors.primarySoft,
    alignItems: "center",
    justifyContent: "center",
  },
  sectionCopy: { flex: 1 },
  sectionTitle: {
    color: colors.text,
    fontFamily: fonts.black,
    fontSize: 16,
  },
  sectionSubtitle: {
    marginTop: 3,
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 10,
    lineHeight: 15,
  },
  thread: { gap: 7 },
  historyItem: { paddingVertical: 10, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border, gap: 5 },
  bubble: {
    maxWidth: "84%",
    paddingHorizontal: 12,
    paddingVertical: 9,
    borderRadius: 15,
  },
  bubbleIncoming: {
    alignSelf: "flex-start",
    backgroundColor: colors.surfaceAlt,
  },
  bubbleMine: {
    alignSelf: "flex-end",
    backgroundColor: colors.primary,
  },
  bubbleText: {
    color: colors.text,
    fontFamily: fonts.regular,
    fontSize: 11,
    lineHeight: 16,
  },
  bubbleTextMine: { color: colors.white },
  blockButton: {
    minHeight: 46,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#F5C7CB",
    backgroundColor: "#FFF5F6",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 7,
  },
  blockText: {
    color: colors.danger,
    fontFamily: fonts.semibold,
    fontSize: 11,
  },
});
