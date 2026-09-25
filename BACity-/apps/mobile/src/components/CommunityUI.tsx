import { PropsWithChildren } from 'react';
import { ScrollView, View, Text, TextInput, Pressable, StyleSheet, ActivityIndicator } from 'react-native';
import { colors } from '../theme/colors';

export function Page({ title, children }: PropsWithChildren<{ title: string }>) {
  return <ScrollView contentContainerStyle={ui.page} keyboardShouldPersistTaps="handled"><Text accessibilityRole="header" style={ui.title}>{title}</Text>{children}</ScrollView>;
}
export function Card({ children }: PropsWithChildren) { return <View style={ui.card}>{children}</View>; }
export function Button({ title, onPress, busy = false }: { title: string; onPress: () => void; busy?: boolean }) {
  return <Pressable accessibilityRole="button" disabled={busy} onPress={onPress} style={[ui.button, busy && { opacity: 0.5 }]}>{busy ? <ActivityIndicator color="#fff" /> : <Text style={ui.buttonText}>{title}</Text>}</Pressable>;
}
export function Field({ label, value, onChange, multiline, secure }: { label: string; value: string; onChange: (value: string) => void; multiline?: boolean; secure?: boolean }) {
  return <View style={{ gap: 6 }}><Text style={ui.text}>{label}</Text><TextInput accessibilityLabel={label} value={value} onChangeText={onChange} multiline={multiline} secureTextEntry={secure} autoCapitalize="none" style={[ui.input, multiline && { minHeight: 100 }]} /></View>;
}
export function Notice({ text }: { text: string | null | undefined }) { return text ? <Text accessibilityRole="alert" style={ui.notice}>{text}</Text> : null; }
export const ui = StyleSheet.create({
  page: { padding: 20, gap: 16, backgroundColor: colors.background, flexGrow: 1, paddingBottom: 48 },
  title: { fontSize: 28, fontWeight: '700', color: colors.text },
  heading: { fontSize: 19, fontWeight: '600', color: colors.text },
  text: { fontSize: 15, lineHeight: 22, color: colors.text },
  muted: { fontSize: 13, lineHeight: 20, color: colors.textMuted },
  card: { padding: 16, borderRadius: 18, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface, gap: 10 },
  input: { borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: 14, color: colors.text, backgroundColor: colors.surface },
  button: { backgroundColor: colors.primary, padding: 14, borderRadius: 12, alignItems: 'center', minHeight: 48 },
  buttonText: { color: '#fff', fontWeight: '600', fontSize: 15 },
  notice: { color: colors.primaryDark, fontSize: 14, lineHeight: 21 },
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
});
