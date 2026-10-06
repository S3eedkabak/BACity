import { StyleSheet, View } from 'react-native';
import { colors } from '../theme/colors';
import { tokens } from '../theme/tokens';
import { SkeletonPulse } from './motion/Motion';

export function LoadingState({ variant = 'feed' }: { variant?: 'feed' | 'detail' | 'saved' }) {
  return <SkeletonPulse style={styles.page}>
    <View style={[styles.hero, variant === 'detail' && styles.detail]} />
    <View style={styles.lineWide} /><View style={styles.line} />
    {variant === 'detail' ? <View style={styles.metadata}><View style={styles.info} /><View style={styles.info} /></View> :
      [0, 1].map(item => <View key={item} style={styles.card}><View style={styles.image} /><View style={styles.copy}><View style={styles.lineWide} /><View style={styles.line} /></View></View>)}
  </SkeletonPulse>;
}
const styles = StyleSheet.create({
  page: { backgroundColor: colors.background, padding: tokens.layout.gutter, gap: tokens.space.lg },
  hero: { aspectRatio: tokens.image.feed, width: '100%', borderRadius: tokens.radius.lg, backgroundColor: colors.skeleton },
  detail: { aspectRatio: .95 },
  lineWide: { height: 18, width: '80%', borderRadius: 6, backgroundColor: colors.skeleton },
  line: { height: 12, width: '56%', borderRadius: 6, backgroundColor: colors.surfaceAlt },
  card: { height: 120, borderRadius: tokens.radius.md, backgroundColor: colors.surface, padding: tokens.space.md, flexDirection: 'row' },
  image: { width: 96, height: 96, borderRadius: tokens.radius.sm, backgroundColor: colors.skeleton },
  copy: { flex: 1, padding: tokens.space.md, gap: tokens.space.md },
  metadata: { flexDirection: 'row', gap: tokens.space.md },
  info: { flex: 1, height: 100, borderRadius: tokens.radius.md, backgroundColor: colors.skeleton },
});
