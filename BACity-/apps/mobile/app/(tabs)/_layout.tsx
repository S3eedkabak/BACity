import { Tabs } from "expo-router";
import { AppIcon } from "../../src/components/AppIcon";
import { TabIcon } from '../../src/components/TabIcon';
import { StyleSheet, Text, View } from "react-native";
import { AnimatedPressable as Pressable } from '../../src/components/motion/Motion';
import { colors } from "../../src/theme/colors";
import { fonts } from "../../src/theme/fonts";
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useMajorTransition } from '../../src/components/loading/LoadingExperience';

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
        <AppIcon name="add" size={24} color={colors.white} />
      </View>
      <Text style={styles.createLabel}>Create</Text>
    </Pressable>
  );
}

export default function TabsLayout() {
  const insets = useSafeAreaInsets();
  const major = useMajorTransition();
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: [styles.tabBar, { height: 72 + insets.bottom, paddingBottom: Math.max(8, insets.bottom) }],
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
            <TabIcon name="home" focused={focused} color={color} size={size} />
          ),
        }}
      />
      <Tabs.Screen
        name="explore"
        options={{
          title: "Explore",
          tabBarIcon: ({ color, size, focused }) => (
            <TabIcon name="search" focused={focused} color={color} size={size} />
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
        listeners={({ navigation }) => ({
          tabPress: () => { if (!navigation.isFocused()) major.begin('map'); },
        })}
        options={{
          title: "Map",
          tabBarIcon: ({ color, size, focused }) => (
            <TabIcon name="map" focused={focused} color={color} size={size} />
          ),
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: "Profile",
          tabBarIcon: ({ color, size, focused }) => (
            <TabIcon name="person" focused={focused} color={color} size={size} />
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
    shadowOpacity: 0,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: -4 },
    elevation: 8,
  },
  label: {
    fontFamily: fonts.semibold,
    fontSize: 11,
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
    shadowOpacity: 0,
    shadowRadius: 7,
    shadowOffset: { width: 0, height: 3 },
    elevation: 4,
  },
  createLabel: {
    color: colors.textMuted,
    fontFamily: fonts.semibold,
    fontSize: 11,
    marginTop: 2,
  },
  pressed: { opacity: 0.82 },
});
