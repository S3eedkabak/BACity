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
        <Ionicons name="add" size={24} color={colors.white} />
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
        tabBarHideOnKeyboard: true,
      }}
    >
      <Tabs.Screen
        name="discover"
        options={{
          title: "Home",
          tabBarIcon: ({ color, size, focused }) => (
            <Ionicons name={focused ? "home" : "home-outline"} color={color} size={size} />
          ),
        }}
      />
      <Tabs.Screen
        name="explore"
        options={{
          title: "Explore",
          tabBarIcon: ({ color, size, focused }) => (
            <Ionicons name={focused ? "search" : "search-outline"} color={color} size={size} />
          ),
        }}
      />
      <Tabs.Screen
        name="contribute"
        options={{
          title: "Create",
          tabBarButton: (props) => <CreateTabButton {...props} />,
        }}
      />
      <Tabs.Screen
        name="map"
        options={{
          title: "Map",
          tabBarIcon: ({ color, size, focused }) => (
            <Ionicons name={focused ? "map" : "map-outline"} color={color} size={size} />
          ),
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: "Profile",
          tabBarIcon: ({ color, size, focused }) => (
            <Ionicons name={focused ? "person" : "person-outline"} color={color} size={size} />
          ),
        }}
      />
      <Tabs.Screen name="saved" options={{ href: null }} />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  tabBar: {
    height: 68,
    paddingTop: 7,
    paddingBottom: 7,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
    backgroundColor: colors.surface,
    shadowColor: colors.text,
    shadowOpacity: 0.07,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: -4 },
    elevation: 8,
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
    paddingTop: 2,
  },
  createCircle: {
    width: 42,
    height: 42,
    borderRadius: 15,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: colors.primaryDark,
    shadowOpacity: 0.18,
    shadowRadius: 7,
    shadowOffset: { width: 0, height: 3 },
    elevation: 4,
  },
  createLabel: {
    color: colors.textMuted,
    fontFamily: fonts.semibold,
    fontSize: 9,
    marginTop: 2,
  },
  pressed: { opacity: 0.82, transform: [{ scale: 0.97 }] },
});
