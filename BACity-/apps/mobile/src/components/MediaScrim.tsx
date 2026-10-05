import { useId } from 'react';
import { StyleSheet, View } from 'react-native';
import Svg, { Defs, LinearGradient, Rect, Stop } from 'react-native-svg';

/** Local vector scrim keeps photo-backed text readable without hiding the whole image. */
export function MediaScrim() {
  const id = useId().replace(/:/g, '');
  return <View pointerEvents="none" style={StyleSheet.absoluteFill} accessibilityElementsHidden importantForAccessibility="no-hide-descendants"><Svg width="100%" height="100%"><Defs><LinearGradient id={id} x1="0" y1="0" x2="0" y2="1"><Stop offset="0" stopColor="#18151F" stopOpacity=".08" /><Stop offset=".45" stopColor="#18151F" stopOpacity=".12" /><Stop offset="1" stopColor="#18151F" stopOpacity=".9" /></LinearGradient></Defs><Rect width="100%" height="100%" fill={`url(#${id})`} /></Svg></View>;
}
