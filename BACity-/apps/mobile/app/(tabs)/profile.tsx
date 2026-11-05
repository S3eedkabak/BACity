import { ContentStages } from "../../src/components/navigation/SceneMotion";
import { SegmentedControl } from "../../src/components/interactions/SegmentedControl";
import { SectionTransition } from "../../src/components/navigation/SceneMotion";
import { TabScene } from "../../src/components/navigation/SceneMotion";
import { SettingsNavList } from "../../src/components/interactions/NavListCard";
import { AppearanceSettings } from "../../src/components/interactions/AppearanceSettings";
import { useQuery } from "@tanstack/react-query";
import { themedStyles, useThemeRevision } from "../../src/theme/appearance";
import { useEffect, useRef, useState } from "react";
import { FlatList, StyleSheet, Text, View } from "react-native";
import { AnimatedPressable as Pressable } from "../../src/components/motion/Motion";
import { SafeAreaView } from "../../src/components/navigation/ContentSafeArea";
import { AppIcon } from "../../src/components/AppIcon";
import { router } from "expo-router";
import { apiRequest } from "../../src/api/client";
import {
  getProfile,
  getProfileHistory,
  type PublicProfile,
} from "../../src/api/community";
import { Chip } from "../../src/components/CommunityUI";
import { EmptyState } from "../../src/components/EmptyState";
import {
  Avatar,
  IconButton,
  ListItem,
  OverflowMenu,
  ScreenHeader,
  SkeletonList,
  Stat,
} from "../../src/components/SocialUI";
import { useAuthStore } from "../../src/store/authStore";
import { colors } from "../../src/theme/colors";
import { fonts } from "../../src/theme/fonts";

type Tab = "contributions" | "reviews" | "collections";
function ProfileScreen() {
  useThemeRevision();
  const user = useAuthStore((state) => state.user);
  const token = useAuthStore((state) => state.token);
  const logout = useAuthStore((state) => state.logout);
  const profileQuery = useQuery({
    queryKey: ["profile", user?.id],
    queryFn: () => getProfile(user!.id),
    enabled: !!user,
  });
  const profile = profileQuery.data;
  const [tab, setTab] = useState<Tab>("contributions");
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [more, setMore] = useState(false);
  const [menu, setMenu] = useState(false);

  const historyRequest = useRef(0);
  async function load(append = false) {
    if (!user) return;
    const request = ++historyRequest.current;
    setLoading(true);
    try {
      let result: any[];
      if (tab === "collections")
        result = (
          await apiRequest<any[]>("/community/collections", { auth: true })
        ).filter((item) => item.user_id === user.id);
      else
        result = await getProfileHistory(
          user.id,
          tab,
          append ? items.length : 0,
          12,
        );
      if (request !== historyRequest.current) return;
      setItems((current) => (append ? [...current, ...result] : result));
      setMore(tab !== "collections" && result.length === 12);
      setError("");
    } catch (e: any) {
      if (request === historyRequest.current) setError(e.message);
    } finally {
      if (request === historyRequest.current) setLoading(false);
    }
  }
  useEffect(() => {
    setItems([]);
    void load(false);
    return () => {
      historyRequest.current++;
    };
  }, [user?.id, tab]);
  async function signOut() {
    await logout();
    router.replace("/welcome");
  }
  if (!token || !user)
    return (
      <SafeAreaView style={styles.safe} edges={["top"]}>
        <View style={styles.guest}>
          <AppIcon name="people" size={42} color={colors.primary} />
          <Text style={styles.guestTitle}>Your city, your profile.</Text>
          <Text style={styles.guestText}>
            Save plans, follow local voices and contribute what makes Bratislava
            useful.
          </Text>
          <Pressable
            style={styles.primary}
            onPress={() =>
              router.push({ pathname: "/auth", params: { mode: "register" } })
            }
          >
            <Text style={styles.primaryText}>Create an account</Text>
          </Pressable>
          <Pressable
            style={styles.secondary}
            onPress={() =>
              router.push({ pathname: "/auth", params: { mode: "login" } })
            }
          >
            <Text style={styles.secondaryText}>Log in</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  const visible =
    profile ??
    ({
      ...user,
      contributions_count: 0,
      reviews_count: 0,
      followers: 0,
      following: 0,
      reputation_level: user.role === "GUIDE" ? "Local Guide" : "Contributor",
    } as PublicProfile);
  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ScreenHeader
        title="Profile"
        back={false}
        right={
          <IconButton
            icon="menu-outline"
            label="Profile menu"
            onPress={() => setMenu(true)}
          />
        }
      />
      <FlatList
        data={items}
        keyExtractor={(item, index) => item.id || String(index)}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
        ListHeaderComponent={
          <ContentStages>
            <View style={styles.identity}>
              <Avatar
                uri={visible.avatar_url}
                name={visible.display_name || user.email}
                size={56}
              />
              <View style={styles.identityCopy}>
                <View style={styles.nameRow}>
                  <Text style={styles.name} numberOfLines={1}>
                    {visible.display_name || "City explorer"}
                  </Text>
                  {visible.identity_verified && (
                    <AppIcon
                      name="checkmark-circle"
                      size={18}
                      color={colors.free}
                    />
                  )}
                </View>
                <Text style={styles.location}>
                  {visible.neighborhood || visible.city || "Bratislava"}
                </Text>
                <Text style={styles.reputation}>
                  {visible.role === "GUIDE" ? "Local Guide · " : ""}
                  {visible.reputation_level}
                </Text>
              </View>
            </View>
            {visible.bio ? <Text style={styles.bio}>{visible.bio}</Text> : null}
            <View style={styles.stats}>
              <Stat
                value={profile?.contributions_count ?? "—"}
                label="Contributions"
                onPress={() => setTab("contributions")}
              />
              <Stat
                value={profile?.followers ?? "—"}
                label="Followers"
                onPress={() =>
                  router.push({
                    pathname: "/social/followers",
                    params: { userId: user.id },
                  })
                }
              />
              <Stat
                value={profile?.following ?? "—"}
                label="Following"
                onPress={() =>
                  router.push({
                    pathname: "/social/following",
                    params: { userId: user.id },
                  })
                }
              />
            </View>
            <View
              style={{
                flexDirection: "row",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <Text style={{ color: colors.textMuted, fontSize: 13 }}>
                Your public activity
              </Text>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Edit profile"
                onPress={() => router.push("/account")}
                style={{
                  minHeight: 48,
                  justifyContent: "center",
                  paddingHorizontal: 12,
                }}
              >
                <Text
                  style={{
                    color: colors.primaryDark,
                    fontSize: 13,
                    fontWeight: "600",
                  }}
                >
                  Edit profile
                </Text>
              </Pressable>
            </View>
            <SegmentedControl
              label="Profile activity"
              options={(
                ["contributions", "reviews", "collections"] as Tab[]
              ).map((id) => ({ id, label: id[0].toUpperCase() + id.slice(1) }))}
              value={tab}
              onChange={setTab}
            />
            {error ? <Text style={styles.error}>{error}</Text> : null}
            {loading && !items.length ? <SkeletonList rows={3} /> : null}
          </ContentStages>
        }
        ListEmptyComponent={
          !loading ? (
            <SectionTransition identity={tab}>
              <EmptyState
                compact
                title={`No ${tab} yet`}
                subtitle={
                  tab === "collections"
                    ? "Create a collection from your saved places and events."
                    : `Your public ${tab} will appear here.`
                }
                action={tab === "collections" ? "Create collection" : undefined}
                onAction={
                  tab === "collections"
                    ? () => router.push("/collection")
                    : undefined
                }
              />
            </SectionTransition>
          ) : null
        }
        renderItem={({ item }) => (
          <ListItem
            icon={
              tab === "contributions"
                ? item.kind === "event"
                  ? "calendar-outline"
                  : "location-outline"
                : tab === "reviews"
                  ? "star-outline"
                  : "albums-outline"
            }
            title={item.title || item.target_name || item.kind || "Collection"}
            subtitle={
              tab === "reviews"
                ? item.body
                : tab === "collections"
                  ? `${item.items?.length || 0} items · ${item.public ? "Public" : "Private"}`
                  : new Date(item.created_at).toLocaleDateString()
            }
            onPress={
              item.published_id
                ? () =>
                    item.kind === "event"
                      ? router.push(`/event/${item.published_id}`)
                      : item.kind === "place"
                        ? router.push(`/place/${item.published_id}`)
                        : router.push(`/utility/${item.published_id}`)
                : undefined
            }
          />
        )}
        ListFooterComponent={
          more ? (
            <Text style={styles.more} onPress={() => load(true)}>
              {loading ? "Loading…" : "Load more"}
            </Text>
          ) : null
        }
      />
      <OverflowMenu
        visible={menu}
        title="Profile menu"
        onClose={() => setMenu(false)}
      >
        <SettingsNavList title="Your city">
          <ListItem
            icon="chatbubble-outline"
            title="Messages"
            subtitle="Your private conversations"
            onPress={() => {
              setMenu(false);
              router.push("/messages");
            }}
          />
          <ListItem
            icon="bookmark-outline"
            title="Saved"
            subtitle="Your personal event library"
            onPress={() => {
              setMenu(false);
              router.push("/(tabs)/saved");
            }}
          />
          <ListItem
            icon="pulse-outline"
            title="Your activity"
            subtitle="Contributions, decisions and appeals"
            onPress={() => {
              setMenu(false);
              router.push("/activity");
            }}
          />
          <ListItem
            icon="albums-outline"
            title="Collections"
            onPress={() => {
              setMenu(false);
              router.push("/collections");
            }}
          />
          <ListItem
            icon="people-outline"
            title="Following"
            subtitle="People, places and local interests"
            onPress={() => {
              setMenu(false);
              router.push("/following");
            }}
          />
        </SettingsNavList>
        <SettingsNavList title="Tools">
          {["ORGANIZER", "ADMIN"].includes(user.role) && (
            <ListItem
              icon="business-outline"
              title="Organizer tools"
              onPress={() => {
                setMenu(false);
                router.push("/organizer");
              }}
            />
          )}
          {["GUIDE", "ADMIN"].includes(user.role) && (
            <ListItem
              icon="navigate-outline"
              title="Local Guide tools"
              subtitle="Your public contribution history"
              onPress={() => {
                setMenu(false);
                router.push("/activity");
              }}
            />
          )}
          {["MODERATOR", "ADMIN"].includes(user.role) && (
            <ListItem
              icon="shield-checkmark-outline"
              title="Moderator tools"
              onPress={() => {
                setMenu(false);
                router.push("/moderator");
              }}
            />
          )}
        </SettingsNavList>
        <SettingsNavList title="Account & support">
          <ListItem
            icon="settings-outline"
            title="Settings & privacy"
            onPress={() => {
              setMenu(false);
              router.push("/account");
            }}
          />
          {user.role === "ADMIN" && (
            <ListItem
              icon="lock-closed-outline"
              title="Privacy review"
              subtitle="Audited administrative access"
              onPress={() => {
                setMenu(false);
                router.push("/privacy-admin");
              }}
            />
          )}
          <ListItem
            icon="sparkles-outline"
            title="BACity+"
            subtitle="Access and subscription management"
            onPress={() => {
              setMenu(false);
              router.push("/plus");
            }}
          />
          <ListItem
            icon="ban-outline"
            title="Blocked users"
            onPress={() => {
              setMenu(false);
              router.push("/blocked");
            }}
          />
          <ListItem icon="log-out-outline" title="Log out" onPress={signOut} />
        </SettingsNavList>
        <AppearanceSettings />
      </OverflowMenu>
    </SafeAreaView>
  );
}

const styles = themedStyles(() => ({
  safe: { flex: 1, backgroundColor: colors.background },
  content: {
    width: "100%",
    maxWidth: 760,
    alignSelf: "center",
    paddingHorizontal: 18,
    paddingBottom: 92,
    flexGrow: 1,
  },
  guest: { flex: 1, justifyContent: "center", padding: 28 },
  guestTitle: {
    color: colors.text,
    fontFamily: fonts.black,
    fontWeight: "800",
    fontSize: 30,
    marginTop: 8,
  },
  guestText: {
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 14,
    lineHeight: 21,
    marginVertical: 12,
  },
  primary: {
    minHeight: 52,
    borderRadius: 17,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 12,
  },
  primaryText: {
    color: colors.white,
    fontFamily: fonts.semibold,
    fontWeight: "600",
  },
  secondary: { minHeight: 52, alignItems: "center", justifyContent: "center" },
  secondaryText: {
    color: colors.text,
    fontFamily: fonts.semibold,
    fontWeight: "600",
  },
  identity: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    marginTop: 8,
    paddingVertical: 12,
  },
  identityCopy: { alignItems: "flex-start", minWidth: 0, flex: 1 },
  nameRow: { flexDirection: "row", alignItems: "center", gap: 6 },
  name: {
    flexShrink: 1,
    color: colors.text,
    fontFamily: fonts.black,
    fontWeight: "800",
    fontSize: 21,
    letterSpacing: -0.3,
  },
  location: {
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 14,
    marginTop: 8,
  },
  reputation: {
    color: colors.primaryDark,
    fontFamily: fonts.semibold,
    fontWeight: "600",
    fontSize: 13,
    marginTop: 6,
  },
  bio: {
    color: colors.text,
    fontFamily: fonts.regular,
    fontSize: 16,
    lineHeight: 24,
    marginTop: 8,
    marginBottom: 12,
  },
  stats: {
    flexDirection: "row",
    marginTop: 8,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  error: { color: colors.danger, marginVertical: 10 },
  more: { color: colors.primaryDark, textAlign: "center", padding: 18 },
}));

export default function AnimatedProfileScreen() {
  return (
    <TabScene>
      <ProfileScreen />
    </TabScene>
  );
}
