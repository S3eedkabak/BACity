import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors } from "../../src/theme/colors";
import { fonts } from "../../src/theme/fonts";

function CreateTabButton(props: any) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel="Create"
      onPress={props.onPress}
      onLongPress={props.onLongPress}
      style={({ pressed }) => [styles.createSlot, pressed && styles.pressed]}
    >
      <View style={styles.createCircle}>
        <Ionicons name="add" size={28} color={colors.white} />
      </View>
      <Text style={styles.createLabel}>Create</Text>
    </Pressable>
  );
}

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: styles.tabBar,
        tabBarActiveTintColor: colors.primaryDark,
        tabBarInactiveTintColor: colors.textMuted,
        tabBarLabelStyle: styles.label,
        tabBarIconStyle: styles.icon,
      }}
    >
      <Tabs.Screen
        name="discover"
        options={{
          title: "Discover",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="home-outline" color={color} size={size} />
          ),
        }}
      />
      <Tabs.Screen
        name="map"
        options={{
          title: "Map",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="map-outline" color={color} size={size} />
          ),
        }}
      />
      <Tabs.Screen
        name="create"
        options={{
          title: "Create",
          tabBarButton: (props) => <CreateTabButton {...props} />,
        }}
      />
      <Tabs.Screen
        name="saved"
        options={{
          title: "Saved",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="bookmark-outline" color={color} size={size} />
          ),
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: "Profile",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="person-outline" color={color} size={size} />
          ),
        }}
      />
      <Tabs.Screen name="explore" options={{ href: null }} />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  tabBar: {
    position: "absolute",
    left: 14,
    right: 14,
    bottom: 12,
    height: 72,
    paddingTop: 8,
    paddingBottom: 8,
    borderTopWidth: 0,
    borderRadius: 26,
    backgroundColor: "rgba(255,255,255,0.98)",
    shadowColor: colors.text,
    shadowOpacity: 0.12,
    shadowRadius: 22,
    shadowOffset: { width: 0, height: 10 },
    elevation: 12,
  },
  label: {
    fontFamily: fonts.semibold,
    fontSize: 9,
    marginBottom: 1,
  },
  icon: { marginTop: 1 },
  createSlot: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    marginTop: -20,
  },
  createCircle: {
    width: 54,
    height: 54,
    borderRadius: 19,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 4,
    borderColor: colors.background,
    shadowColor: colors.primaryDark,
    shadowOpacity: 0.28,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 7 },
    elevation: 8,
  },
  createLabel: {
    color: colors.textMuted,
    fontFamily: fonts.semibold,
    fontSize: 9,
    marginTop: 2,
  },
  pressed: { opacity: 0.82, transform: [{ scale: 0.97 }] },
});
