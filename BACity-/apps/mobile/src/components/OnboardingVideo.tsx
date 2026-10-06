import { useEffect, useState } from 'react';
import { AppState, Image, StyleSheet, View } from 'react-native';
import { useIsFocused } from '@react-navigation/native';
import { Video, ResizeMode } from 'expo-av';
import Animated, { cancelAnimation, useAnimatedStyle, useReducedMotion, useSharedValue, withTiming } from 'react-native-reanimated';
import { colors } from '../theme/colors';
/** Onboarding ONLY. Source is a continuous aerial shot, so hold its final frame. */
export function OnboardingVideo({ height }: { height: number }) {
  const focused = useIsFocused();
  const reduced = useReducedMotion();
  const [active, setActive] = useState(AppState.currentState === 'active');
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [finished, setFinished] = useState(false);
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
  return <View style={[styles.frame, { height }]} accessibilityLabel="Bratislava Castle">
    <Image source={require('../../assets/video/bratislava-poster.jpg')} style={StyleSheet.absoluteFill} resizeMode="cover" />
    {!failed && !reduced && <Animated.View style={[StyleSheet.absoluteFill, reveal]}>
      <Video source={require('../../assets/video/bratislava-onboarding.mp4')} style={StyleSheet.absoluteFill}
        videoStyle={{ width: '100%', height: '100%' }}
        resizeMode={ResizeMode.COVER} useNativeControls={false} isMuted shouldPlay={focused && active && !finished} isLooping={false}
        onPlaybackStatusUpdate={status => { if (status.isLoaded && status.didJustFinish) setFinished(true); }}
        onReadyForDisplay={() => setReady(true)} onError={() => { setFailed(true); if (__DEV__) console.warn('[OnboardingVideo] playback unavailable; using bundled poster'); }} />
    </Animated.View>}
  </View>;
}
const styles = StyleSheet.create({ frame: { width: '100%', overflow: 'hidden', borderRadius: 28, backgroundColor: colors.surface } });
