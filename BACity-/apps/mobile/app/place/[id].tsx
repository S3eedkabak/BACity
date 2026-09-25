import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { Linking, Pressable, StyleSheet, Text, View } from "react-native";
import { apiRequest } from "../../src/api/client";
import { Page, Card, Notice } from "../../src/components/CommunityUI";
import { Discussion } from "../../src/components/Discussion";
import { colors } from "../../src/theme/colors";
import { fonts } from "../../src/theme/fonts";

export default function Place() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [place, setPlace] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiRequest(`/community/places/${id}`)
      .then(setPlace)
      .catch((e) => setError(e.message));
  }, [id]);

  function openMap() {
    if (place?.latitude == null || place?.longitude == null) return;
    void Linking.openURL(
      `https://www.openstreetmap.org/?mlat=${place.latitude}&mlon=${place.longitude}#map=18/${place.latitude}/${place.longitude}`
    );
  }

  return (
    <Page title={place?.name ?? "Place"}>
      <Notice text={error} />

      {place && (
        <>
          <View style={styles.hero}>
            <View style={styles.heroIcon}>
              <Ionicons name="location" size={30} color={colors.white} />
            </View>
            <Text style={styles.name}>{place.name}</Text>
            <Text style={styles.address}>{place.address || "Bratislava"}</Text>

            <View style={styles.badges}>
              {!!place.trust_level && (
                <View style={styles.badge}>
                  <Ionicons name="shield-checkmark-outline" size={12} color={colors.primaryDark} />
                  <Text style={styles.badgeText}>{String(place.trust_level).replaceAll("_", " ")}</Text>
                </View>
              )}
              {!!place.operational_status && (
                <View style={styles.badge}>
                  <View
                    style={[
                      styles.statusDot,
                      place.operational_status === "open"
                        ? styles.statusOpen
                        : styles.statusUnknown,
                    ]}
                  />
                  <Text style={styles.badgeText}>
                    {String(place.operational_status).replaceAll("_", " ")}
                  </Text>
                </View>
              )}
            </View>
          </View>

          <Card>
            <View style={styles.infoRow}>
              <View style={styles.infoIcon}>
                <Ionicons name="information-circle-outline" size={20} color={colors.primaryDark} />
              </View>
              <View style={styles.infoCopy}>
                <Text style={styles.infoTitle}>About this place</Text>
                <Text style={styles.description}>
                  {place.description || "No description has been added yet."}
                </Text>
              </View>
            </View>

            {(place.latitude != null && place.longitude != null) && (
              <Pressable
                onPress={openMap}
                style={({ pressed }) => [styles.mapButton, pressed && styles.pressed]}
              >
                <Ionicons name="navigate-outline" size={17} color={colors.white} />
                <Text style={styles.mapButtonText}>Open on map</Text>
              </Pressable>
            )}
          </Card>

          <Discussion id={id} kind="place" />
        </>
      )}
    </Page>
  );
}

const styles = StyleSheet.create({
  hero: {
    alignItems: "center",
    paddingVertical: 12,
  },
  heroIcon: {
    width: 86,
    height: 86,
    borderRadius: 31,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: colors.primaryDark,
    shadowOpacity: 0.22,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 8 },
    elevation: 5,
  },
  name: {
    marginTop: 14,
    color: colors.text,
    fontFamily: fonts.black,
    fontSize: 27,
    letterSpacing: -0.75,
    textAlign: "center",
  },
  address: {
    marginTop: 5,
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 12,
    textAlign: "center",
  },
  badges: {
    marginTop: 11,
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
    textTransform: "capitalize",
  },
  statusDot: { width: 6, height: 6, borderRadius: 3 },
  statusOpen: { backgroundColor: colors.free },
  statusUnknown: { backgroundColor: colors.accent },
  infoRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 11,
  },
  infoIcon: {
    width: 42,
    height: 42,
    borderRadius: 15,
    backgroundColor: colors.primarySoft,
    alignItems: "center",
    justifyContent: "center",
  },
  infoCopy: { flex: 1 },
  infoTitle: {
    color: colors.text,
    fontFamily: fonts.black,
    fontSize: 16,
  },
  description: {
    marginTop: 5,
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 12,
    lineHeight: 18,
  },
  mapButton: {
    minHeight: 50,
    borderRadius: 17,
    backgroundColor: colors.text,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  mapButtonText: {
    color: colors.white,
    fontFamily: fonts.semibold,
    fontSize: 12,
  },
  pressed: { opacity: 0.88, transform: [{ scale: 0.985 }] },
});
