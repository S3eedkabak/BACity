import { useLocalSearchParams } from "expo-router";
import { useRoute } from "@react-navigation/native";
import { StyleSheet, View } from "react-native";
import {
  SafeAreaView as NativeSafeArea,
  useSafeAreaInsets,
  type Edge,
  type EdgeMode,
  type SafeAreaViewProps,
} from "react-native-safe-area-context";
/** Resolve insets before layout, using this screen's identity even while cached.
 * React Navigation recommends hook-based insets to avoid native view flicker.
 */
export function SafeAreaView({ edges, style, mode = 'padding', ...props }: SafeAreaViewProps) {
  const route = useRoute();
  const insets = useSafeAreaInsets();
  const params = useLocalSearchParams<{ districtMorph?: string }>();
  const ownsTop = (route.name === 'area-events' && !!params.districtMorph) ||
    ['discover','explore','profile','map','saved','contribute','welcome','index'].includes(route.name);
  const selected = Object.fromEntries((['top','right','bottom','left'] as Edge[]).map(edge => [edge,
    edge === 'top' && !ownsTop ? 'off' : edges == null ? 'additive' : Array.isArray(edges) ? edges.includes(edge) ? 'additive' : 'off' : (edges as Partial<Record<Edge,EdgeMode>>)[edge] ?? 'off',
  ])) as Record<Edge, EdgeMode>;
  // Keep the Login page's existing native inset implementation and stack header.
  if (route.name === 'auth') return <NativeSafeArea {...props} style={style} mode={mode} edges={selected} />;
  const flat = (StyleSheet.flatten(style) ?? {}) as Record<string, number>;
  const spacing: Record<string, number> = {};
  for (const edge of ['top','right','bottom','left'] as Edge[]) {
    const suffix = edge[0].toUpperCase() + edge.slice(1);
    const key = mode + suffix;
    const current = flat[key] ?? flat[mode + (edge === 'top' || edge === 'bottom' ? 'Vertical' : 'Horizontal')] ?? flat[mode] ?? 0;
    spacing[key] = selected[edge] === 'off' ? current : selected[edge] === 'maximum' ? Math.max(current, insets[edge]) : current + insets[edge];
  }
  return <View {...props} style={[style, spacing]} />;
}
