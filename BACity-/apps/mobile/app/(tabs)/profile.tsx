import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import {
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { apiRequest } from "../../src/api/client";
import { BrandMark } from "../../src/components/BrandMark";
import { useAuthStore } from "../../src/store/authStore";
import { colors } from "../../src/theme/colors";
import { fonts } from "../../src/theme/fonts";

type PublicProfile = {
  id: string;
  display_name: string | null;
  avatar_url: string | null;
  bio: string | null;
  city: string;
  neighborhood: string | null;
  interests: string[];
  role: string;
  identity_verified: boolean;
  reputation_level: string;
  followers: number;
  following: number;
};

const MENU = [
  { label: "Your contributions", subtitle: "Submission status and appeals", icon: "create-outline" as const, route: "/community?section=submissions" as const },
  { label: "Messages", subtitle: "Received messages and member conversations", icon: "chatbubbles-outline" as const, route: "/community?section=messages" as const },
  { label: "Notifications", subtitle: "Community updates", icon: "notifications-outline" as const, route: "/community?section=notifications" as const },
  { label: "Collections", subtitle: "Curated events, places and utilities", icon: "albums-outline" as const, route: "/community?section=collections" as const },
  {
    label: "Community",
    subtitle: "People, guides, utilities and notifications",
    icon: "people-outline" as const,
    route: "/community" as const,
  },
  {
    label: "Account & preferences",
    subtitle: "Profile, privacy and verification",
    icon: "options-outline" as const,
    route: "/account" as const,
  },
  {
    label: "Organizer dashboard",
    subtitle: "Claims, events and audience analytics",
    icon: "business-outline" as const,
    route: "/organizer" as const,
  },
];

export default function ProfileScreen() {
  const user = useAuthStore((s) => s.user);
  const token = useAuthStore((s) => s.token);
  const logout = useAuthStore((s) => s.logout);
  const [profile, setProfile] = useState<PublicProfile | null>(null);

  useEffect(() => {
    let active = true;
    if (!token || !user) {
      setProfile(null);
      return;
    }

    apiRequest<PublicProfile>(`/community/profiles/${user.id}`, { auth: true })
      .then((result) => {
        if (active) setProfile(result);
      })
      .catch(() => {
        if (active) setProfile(null);
      });

    return () => {
      active = false;
    };
  }, [token, user?.id]);

  if (!token || !user) {
    return (
      <SafeAreaView style={styles.safe} edges={["top"]}>
        <View style={styles.guest}>
          <BrandMark />
          <View style={styles.guestArt}>
            <View style={styles.guestGlowOne} />
            <View style={styles.guestGlowTwo} />
            <Ionicons name="people-outline" size={36} color={colors.white} />
          </View>
          <Text style={styles.guestTitle}>Your city gets better when it knows you.</Text>
          <Text style={styles.guestText}>
            Save plans, follow local guides and contribute the places worth knowing.
          </Text>
          <Pressable
            style={({ pressed }) => [styles.primary, pressed && styles.pressed]}
            onPress={() => router.push({ pathname: "/auth", params: { mode: "register" } })}
          >
            <Text style={styles.primaryText}>Create an account</Text>
          </Pressable>
          <Pressable
            style={styles.secondary}
            onPress={() => router.push({ pathname: "/auth", params: { mode: "login" } })}
          >
            <Text style={styles.secondaryText}>Log in</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  const name = user.display_name || "City explorer";
  const initial = (user.display_name || user.email)[0].toUpperCase();
  const visibleProfile = profile ?? {
    id: user.id,
    display_name: user.display_name,
    avatar_url: user.avatar_url,
    bio: user.bio,
    city: user.city,
    neighborhood: user.neighborhood,
    interests: user.interests,
    role: user.role,
    identity_verified: user.identity_verified,
    reputation_level: user.role === "GUIDE" ? "Local Guide" : "Contributor",
    followers: 0,
    following: 0,
  };

  async function signOut() {
    await logout();
    router.replace("/welcome");
  }

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.topbar}>
          <BrandMark compact />
          <Pressable style={styles.settings} onPress={() => router.push("/account")}>
            <Ionicons name="settings-outline" size={19} color={colors.text} />
          </Pressable>
        </View>

        <View style={styles.hero}>
          <View style={styles.avatarWrap}>
            {visibleProfile.avatar_url ? (
              <Image source={{ uri: visibleProfile.avatar_url }} style={styles.avatarImage} />
            ) : (
              <View style={styles.avatar}>
                <Text style={styles.avatarText}>{initial}</Text>
              </View>
            )}
            {visibleProfile.identity_verified && (
              <View style={styles.verified}>
                <Ionicons name="checkmark" size={12} color={colors.white} />
              </View>
            )}
          </View>

          <Text style={styles.name}>{name}</Text>
          <View style={styles.roleRow}>
            <Text style={styles.handle}>
              {visibleProfile.neighborhood || visibleProfile.city || "Bratislava"}
            </Text>
            {visibleProfile.role === "GUIDE" && (
              <View style={styles.guideBadge}>
                <Ionicons name="navigate" size={11} color={colors.primaryDark} />
                <Text style={styles.guideText}>Local Guide</Text>
              </View>
            )}
          </View>

          {!!visibleProfile.bio && <Text style={styles.bio}>{visibleProfile.bio}</Text>}

          <View style={styles.stats}>
            <View style={styles.stat}>
              <Text style={styles.statValue}>{visibleProfile.following}</Text>
              <Text style={styles.statLabel}>Following</Text>
            </View>
            <View style={styles.statDivider} />
            <View style={styles.stat}>
              <Text style={styles.statValue}>{visibleProfile.followers}</Text>
              <Text style={styles.statLabel}>Followers</Text>
            </View>
            <View style={styles.statDivider} />
            <View style={styles.stat}>
              <Text style={styles.statValue}>{visibleProfile.reputation_level}</Text>
              <Text style={styles.statLabel}>Reputation</Text>
            </View>
          </View>
        </View>

        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Your city profile</Text>
          <Pressable onPress={() => router.push("/account")}>
            <Text style={styles.edit}>Edit</Text>
          </Pressable>
        </View>

        <View style={styles.tasteCard}>
          <View style={styles.tasteIcon}>
            <Ionicons name="sparkles-outline" size={20} color={colors.primaryDark} />
          </View>
          <View style={styles.tasteCopy}>
            <Text style={styles.tasteTitle}>Your interests</Text>
            <Text style={styles.tasteText}>
              {visibleProfile.interests.length
                ? visibleProfile.interests.join(" · ")
                : "Save and follow a few things to shape your recommendations."}
            </Text>
          </View>
        </View>

        <View style={styles.menu}>
          {MENU.map((item) => (
            <Pressable
              key={item.label}
              onPress={() => router.push(item.route)}
              style={({ pressed }) => [styles.menuRow, pressed && styles.menuPressed]}
            >
              <View style={styles.menuIcon}>
                <Ionicons name={item.icon} size={19} color={colors.primaryDark} />
              </View>
              <View style={styles.menuCopy}>
                <Text style={styles.menuTitle}>{item.label}</Text>
                <Text style={styles.menuSubtitle}>{item.subtitle}</Text>
              </View>
              <Ionicons name="chevron-forward" size={17} color={colors.textMuted} />
            </Pressable>
          ))}
        </View>

        <Pressable style={styles.logout} onPress={signOut}>
          <Ionicons name="log-out-outline" size={18} color={colors.danger} />
          <Text style={styles.logoutText}>Log out</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  content: { paddingHorizontal: 18, paddingBottom: 112 },
  guest: {
    flex: 1,
    paddingHorizontal: 20,
    paddingTop: 18,
    paddingBottom: 110,
  },
  guestArt: {
    height: 230,
    borderRadius: 30,
    marginTop: 36,
    marginBottom: 28,
    backgroundColor: colors.text,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  guestGlowOne: {
    position: "absolute",
    width: 190,
    height: 190,
    borderRadius: 95,
    backgroundColor: colors.primary,
    left: -35,
    top: -25,
    opacity: 0.92,
  },
  guestGlowTwo: {
    position: "absolute",
    width: 170,
    height: 170,
    borderRadius: 85,
    backgroundColor: colors.accent,
    right: -45,
    bottom: -50,
    opacity: 0.65,
  },
  guestTitle: {
    color: colors.text,
    fontFamily: fonts.black,
    fontSize: 31,
    lineHeight: 34,
    letterSpacing: -1,
  },
  guestText: {
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 14,
    lineHeight: 21,
    marginTop: 10,
    marginBottom: 24,
  },
  primary: {
    minHeight: 55,
    borderRadius: 18,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  primaryText: { color: colors.white, fontFamily: fonts.black, fontSize: 13 },
  secondary: {
    minHeight: 51,
    borderRadius: 18,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 10,
  },
  secondaryText: { color: colors.text, fontFamily: fonts.semibold, fontSize: 13 },
  pressed: { opacity: 0.9, transform: [{ scale: 0.985 }] },
  topbar: {
    minHeight: 58,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  settings: {
    width: 42,
    height: 42,
    borderRadius: 15,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  hero: { alignItems: "center", paddingTop: 22, paddingBottom: 26 },
  avatarWrap: { position: "relative" },
  avatar: {
    width: 94,
    height: 94,
    borderRadius: 34,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarImage: { width: 94, height: 94, borderRadius: 34 },
  avatarText: { color: colors.white, fontFamily: fonts.black, fontSize: 34 },
  verified: {
    position: "absolute",
    right: -2,
    bottom: 4,
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: colors.free,
    borderWidth: 3,
    borderColor: colors.background,
    alignItems: "center",
    justifyContent: "center",
  },
  name: {
    color: colors.text,
    fontFamily: fonts.black,
    fontSize: 28,
    letterSpacing: -0.8,
    marginTop: 14,
  },
  roleRow: { flexDirection: "row", alignItems: "center", gap: 8, marginTop: 5 },
  handle: { color: colors.textMuted, fontFamily: fonts.medium, fontSize: 11 },
  guideBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 5,
    borderRadius: 99,
    backgroundColor: colors.primarySoft,
  },
  guideText: { color: colors.primaryDark, fontFamily: fonts.semibold, fontSize: 9 },
  bio: {
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 12,
    lineHeight: 18,
    textAlign: "center",
    maxWidth: 310,
    marginTop: 10,
  },
  stats: {
    width: "100%",
    marginTop: 22,
    paddingVertical: 15,
    paddingHorizontal: 8,
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
    fontSize: 14,
    maxWidth: 100,
    textAlign: "center",
  },
  statLabel: {
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 9,
    marginTop: 3,
  },
  statDivider: { width: 1, height: 28, backgroundColor: colors.border },
  sectionHeader: {
    marginTop: 2,
    marginBottom: 11,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  sectionTitle: {
    color: colors.text,
    fontFamily: fonts.black,
    fontSize: 19,
    letterSpacing: -0.4,
  },
  edit: { color: colors.primaryDark, fontFamily: fonts.semibold, fontSize: 11 },
  tasteCard: {
    padding: 15,
    borderRadius: 22,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  tasteIcon: {
    width: 44,
    height: 44,
    borderRadius: 15,
    backgroundColor: colors.primarySoft,
    alignItems: "center",
    justifyContent: "center",
  },
  tasteCopy: { flex: 1 },
  tasteTitle: { color: colors.text, fontFamily: fonts.black, fontSize: 12 },
  tasteText: {
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 10,
    lineHeight: 15,
    marginTop: 3,
  },
  menu: {
    marginTop: 14,
    backgroundColor: colors.surface,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: "hidden",
  },
  menuRow: {
    minHeight: 70,
    paddingHorizontal: 13,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  menuPressed: { backgroundColor: colors.surfaceAlt },
  menuIcon: {
    width: 42,
    height: 42,
    borderRadius: 15,
    backgroundColor: colors.primarySoft,
    alignItems: "center",
    justifyContent: "center",
  },
  menuCopy: { flex: 1 },
  menuTitle: { color: colors.text, fontFamily: fonts.semibold, fontSize: 12 },
  menuSubtitle: {
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 9,
    lineHeight: 13,
    marginTop: 2,
  },
  logout: {
    marginTop: 18,
    alignSelf: "center",
    minHeight: 44,
    paddingHorizontal: 16,
    flexDirection: "row",
    gap: 7,
    alignItems: "center",
    justifyContent: "center",
  },
  logoutText: { color: colors.danger, fontFamily: fonts.semibold, fontSize: 11 },
});
