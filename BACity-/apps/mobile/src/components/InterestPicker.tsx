import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors } from '../theme/colors';
import { tokens } from '../theme/tokens';
import { EventMedia } from './EventMedia';

export function InterestPicker({ choices, selected, onToggle }: { choices: readonly string[]; selected: string[]; onToggle: (value: string) => void }) {
  return <View style={styles.grid}>{choices.map(category => <Pressable key={category} accessibilityRole="button" accessibilityLabel={category} accessibilityState={{ selected: selected.includes(category) }} onPress={() => onToggle(category)} style={({ pressed }) => [styles.tile, selected.includes(category) && styles.selected, pressed && { opacity: .8 }]}>
    <EventMedia category={category} style={styles.media} /><View style={styles.caption}><Text style={styles.name}>{category}</Text>{selected.includes(category) && <Ionicons name="checkmark-circle" size={20} color={colors.primary} />}</View>
  </Pressable>)}</View>;
}
const styles = StyleSheet.create({ grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 }, tile: { width: '47%', borderRadius: 20, overflow: 'hidden', backgroundColor: colors.surface, borderWidth: 2, borderColor: 'transparent' }, selected: { borderColor: colors.primary }, media: { height: 96 }, caption: { flexDirection: 'row', gap: 6, alignItems: 'center', padding: 12 }, name: { ...tokens.type.metadata, color: colors.text, flex: 1 } });
