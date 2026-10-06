import { StyleSheet, View } from 'react-native';
import { colors } from '../theme/colors';
import { LoadingState } from './LoadingState';

/** Contextual route placeholder. Cold launch is owned solely by StartupScene. */
export function AppLoadingScreen() {
  return <View style={styles.fill}><LoadingState /></View>;
}
const styles = StyleSheet.create({ fill: { flex: 1, backgroundColor: colors.background } });
