import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { colors } from "../../src/theme/colors";
import { fonts } from "../../src/theme/fonts";

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarHideOnKeyboard: true,
        tabBarStyle: {
          position: "absolute",
          left: 18,
          right: 18,
          bottom: 14,
          height: 66,
          paddingTop: 7,
          paddingBottom: 7,
          borderTopWidth: 0,
          borderWidth: 1,
          borderColor: "rgba(255,255,255,0.08)",
          borderRadius: 24,
          backgroundColor: colors.text,
          shadowColor: colors.shadow,
          shadowOpacity: 0.22,
          shadowRadius: 20,
          shadowOffset: { width: 0, height: 9 },
          elevation: 12,
        },
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: "#B9B0B5",
        tabBarLabelStyle: {
          fontFamily: fonts.semibold,
          fontSize: 9,
          marginBottom: 1,
        },
        tabBarIconStyle: { marginTop: 1 },
        tabBarItemStyle: { borderRadius: 18 },
      }}
    >
      <Tabs.Screen name="index" options={{ title: "Home", tabBarIcon: ({ color, size }) => <Ionicons name="home" color={color} size={size} /> }} />
      <Tabs.Screen name="explore" options={{ title: "Explore", tabBarIcon: ({ color, size }) => <Ionicons name="compass-outline" color={color} size={size + 1} /> }} />
      <Tabs.Screen name="map" options={{ title: "Map", tabBarIcon: ({ color, size }) => <Ionicons name="map-outline" color={color} size={size} /> }} />
      <Tabs.Screen name="saved" options={{ title: "Saved", tabBarIcon: ({ color, size }) => <Ionicons name="heart-outline" color={color} size={size} /> }} />
      <Tabs.Screen name="profile" options={{ title: "You", tabBarIcon: ({ color, size }) => <Ionicons name="person-outline" color={color} size={size} /> }} />
    </Tabs>
  );
}
