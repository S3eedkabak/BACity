import { Platform } from 'react-native';
import * as Haptics from 'expo-haptics';
export function selectionHaptic(reduced: boolean) {
  if (Platform.OS !== 'web' && !reduced) void Haptics.selectionAsync().catch(() => {});
}
export function successHaptic(reduced: boolean) {
  if (Platform.OS !== 'web' && !reduced) void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
}
