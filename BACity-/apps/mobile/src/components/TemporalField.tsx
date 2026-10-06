import { StyleSheet, Text, TextInput, View } from 'react-native';
import { AnimatedPressable as Pressable } from './motion/Motion';
import { AppIcon } from "./AppIcon";
import { colors } from '../theme/colors';
import { tokens } from '../theme/tokens';

/** Dependency-free day/time stepper. Editable value preserves precise and arbitrary future input. */
export function TemporalField({ label, value, onChange, mode = 'date' }: { label: string; value: string; onChange: (value: string) => void; mode?: 'date' | 'time' }) {
  function step(direction: number) {
    if (mode === 'time') {
      const match = /^(\d{2}):(\d{2})$/.exec(value);
      const minutes = match ? Number(match[1]) * 60 + Number(match[2]) : 18 * 60;
      const next = ((minutes + direction * 30) % 1440 + 1440) % 1440;
      onChange(`${String(Math.floor(next / 60)).padStart(2, '0')}:${String(next % 60).padStart(2, '0')}`);
    } else {
      const current = new Date(`${value}T12:00:00`);
      const next = Number.isNaN(current.getTime()) ? new Date() : current;
      next.setDate(next.getDate() + direction);
      onChange(`${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, '0')}-${String(next.getDate()).padStart(2, '0')}`);
    }
  }
  return <View style={styles.group}><Text style={styles.label}>{label}</Text><View style={styles.control}>
    <Pressable accessibilityRole="button" accessibilityLabel={`${label}: earlier ${mode === 'date' ? 'day' : 'time'}`} onPress={() => step(-1)} style={styles.button}><AppIcon name="remove" size={22} color={colors.text} /></Pressable>
    <TextInput accessibilityLabel={label} value={value} onChangeText={onChange} placeholder={mode === 'date' ? 'YYYY-MM-DD' : 'HH:MM'} style={styles.value} maxLength={mode === 'date' ? 10 : 5} keyboardType="numbers-and-punctuation" />
    <Pressable accessibilityRole="button" accessibilityLabel={`${label}: later ${mode === 'date' ? 'day' : 'time'}`} onPress={() => step(1)} style={styles.button}><AppIcon name="add" size={22} color={colors.text} /></Pressable>
  </View></View>;
}
const styles = StyleSheet.create({ group: { gap: 8 }, label: { ...tokens.type.metadata, color: colors.textMuted }, control: { flexDirection: 'row', borderRadius: 20, backgroundColor: colors.surface, alignItems: 'center' }, button: { minWidth: 44, minHeight: 52, alignItems: 'center', justifyContent: 'center' }, value: { ...tokens.type.action, color: colors.text, textAlign: 'center', flex: 1, minWidth: 0, paddingVertical: 14 } });
