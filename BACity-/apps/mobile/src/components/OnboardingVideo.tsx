import { useEffect, useState } from 'react';
import { AppState, Image, StyleSheet, View } from 'react-native';
import { useIsFocused } from '@react-navigation/native';
import { Video, ResizeMode } from 'expo-av';
import Animated, { cancelAnimation, useAnimatedStyle, useReducedMotion, useSharedValue, withTiming } from 'react-native-reanimated';
/** Onboarding ONLY. A full-bleed cinematic background, never an embedded player. */
export function OnboardingVideo() {
  const focused = useIsFocused();
  const reduced = useReducedMotion();
  const [active, setActive] = useState(AppState.currentState === 'active');
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const opacity = useSharedValue(0);
  useEffect(() => {
    const listener = AppState.addEventListener('change', status => setActive(status === 'active'));
    return () => listener.remove();
  }, []);
  useEffect(() => {
    opacity.value = withTiming(ready && !failed ? 1 : 0, { duration: reduced ? 0 : 260 });
    return () => cancelAnimation(opacity);
  }, [ready, failed, opacity, reduced]);
  const reveal = useAnimatedStyle(() => ({ opacity: opacity.value }));
  return <View pointerEvents="none" style={styles.frame} accessibilityLabel="Bratislava Castle">
    <Image source={require('../../assets/video/bratislava-poster.jpg')} style={StyleSheet.absoluteFill} resizeMode="cover" />
    {!failed && !reduced && <Animated.View style={[StyleSheet.absoluteFill, reveal]}>
      <Video source={require('../../assets/video/bratislava-onboarding.mp4')} style={StyleSheet.absoluteFill}
        videoStyle={{ width: '100%', height: '100%' }}
        resizeMode={ResizeMode.COVER} useNativeControls={false} isMuted shouldPlay={focused && active} isLooping
        onReadyForDisplay={() => setReady(true)} onError={() => { setFailed(true); if (__DEV__) console.warn('[OnboardingVideo] playback unavailable; using bundled poster'); }} />
    </Animated.View>}
  </View>;
}
const styles = StyleSheet.create({ frame: { ...StyleSheet.absoluteFillObject, overflow: 'hidden', backgroundColor: '#100E12' } });
