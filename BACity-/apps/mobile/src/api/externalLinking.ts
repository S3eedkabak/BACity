import { Alert, Linking } from 'react-native';
import { safeExternalUrl } from './externalUrl';

export const externalLinking = {
  async openURL(value: unknown): Promise<void> {
    const url = safeExternalUrl(value);
    if (!url) {
      Alert.alert('Cannot open link', 'This is not a valid public website link.');
      return;
    }
    try { await Linking.openURL(url); }
    catch { Alert.alert('Cannot open link', 'Please try again later.'); }
  },
};
