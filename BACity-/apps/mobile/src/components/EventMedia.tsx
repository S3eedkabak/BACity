import { ComponentProps, useEffect, useState } from 'react';
import { Image, StyleProp, StyleSheet, Text, View, ViewStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import Svg, { Circle, Path } from 'react-native-svg';
import { tokens } from '../theme/tokens';

type Icon = ComponentProps<typeof Ionicons>['name'];
const motifs: Record<string, { color: string; icon: Icon }> = {
  Music: { color: '#4E355B', icon: 'musical-notes-outline' }, Culture: { color: '#355F58', icon: 'library-outline' },
  Nightlife: { color: '#3D335D', icon: 'moon-outline' }, Arts: { color: '#98463F', icon: 'color-palette-outline' },
  Family: { color: '#426B70', icon: 'people-outline' }, Community: { color: '#686142', icon: 'people-circle-outline' },
};
/** Real artwork only. Failures use local vector identity, never invented photography. */
export function EventMedia({ uri, category, title, style }: { uri?: string | null; category?: string; title?: string; style?: StyleProp<ViewStyle> }) {
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => { setFailed(false); setLoaded(false); }, [uri]);
  const motif = motifs[category || ''] || { color: '#6F4355', icon: 'sparkles-outline' as Icon };
  return <View style={[styles.media, { backgroundColor: motif.color }, style]} accessible={!!title} accessibilityLabel={title ? `Artwork for ${title}` : undefined}>
    <View pointerEvents="none" style={StyleSheet.absoluteFill} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <Svg width="100%" height="100%" viewBox="0 0 400 400" preserveAspectRatio="xMidYMid slice">
        <Circle cx="340" cy="70" r="150" fill="#FFFFFF" opacity=".06" />
        <Path d="M-40 370 C90 40 200 470 460 70 M-40 330 C90 0 200 430 460 30 M-40 290 C90 -40 200 390 460 -10" stroke="#FFFFFF" strokeWidth="2" opacity=".18" fill="none" />
      </Svg>
      <View style={styles.motif}><Ionicons name={motif.icon} size={48} color="rgba(255,255,255,.8)" /><Text style={styles.category}>{category || 'Bratislava'}</Text></View>
    </View>
    {!!uri && !failed && <Image source={{ uri }} style={[StyleSheet.absoluteFill, { opacity: loaded ? 1 : 0 }]} resizeMode="cover" onLoad={() => setLoaded(true)} onError={() => setFailed(true)} accessibilityIgnoresInvertColors />}
  </View>;
}
const styles = StyleSheet.create({ media: { overflow: 'hidden' }, motif: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12 }, category: { ...tokens.type.metadata, color: '#FFFFFF', letterSpacing: 2, textTransform: 'uppercase' } });
