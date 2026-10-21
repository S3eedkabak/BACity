import { useCallback, useEffect, useRef } from 'react';
import { AppState, Platform, StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import Svg, { Path } from 'react-native-svg';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Animated, {
  Easing, cancelAnimation, interpolate, runOnJS, useAnimatedProps, useAnimatedReaction,
  useAnimatedStyle, useReducedMotion, useSharedValue, withTiming,
} from 'react-native-reanimated';
import { colors } from '../theme/colors';
import { fonts } from '../theme/fonts';
import { interpolateRingPath } from './districtMorphGeometry';
import { useDistrictMorph } from './districtMorphState';

export const DISTRICT_SURFACE = '#E987B8';
const AnimatedPath = Animated.createAnimatedComponent(Path);

/** One overlay above the root stack keeps the same geographic surface visible across routes. */
export function DistrictMorphLayer() {
  const host = useRef<View>(null);
  const insets = useSafeAreaInsets();
  const phase = useDistrictMorph(state => state.phase);
  const nonce = useDistrictMorph(state => state.nonce);
  const entry = useDistrictMorph(state => state.entry);
  const viewport = useDistrictMorph(state => state.viewport);
  const areaMounted = useDistrictMorph(state => state.areaMounted);
  const reduced = useReducedMotion();
  const progress = useSharedValue(0);
  const opacity = useSharedValue(1);
  const backdropOpacity = useSharedValue(1);
  const navigationMade = useRef(false);
  const backMade = useRef(false);

  const openRoute = useCallback((expected: number) => {
    const current = useDistrictMorph.getState();
    if (current.nonce !== expected || current.phase !== 'morphing' || !current.entry || navigationMade.current) return;
    navigationMade.current = true;
    router.push({...current.entry.route, params:{...current.entry.route.params,districtMorph:'1'}});
  }, []);
  const popRoute = useCallback((expected: number) => {
    const current = useDistrictMorph.getState();
    if (current.nonce !== expected || current.phase !== 'returning' || backMade.current) return;
    backMade.current = true;
    if (router.canGoBack()) router.back();
    else router.replace('/(tabs)/map');
  }, []);
  const finishOpen = useCallback((expected: number) => {
    openRoute(expected);
    useDistrictMorph.getState().areaVisible(expected);
  }, [openRoute]);
  const finishReturn = useCallback((expected: number) => {
    popRoute(expected);
    if (useDistrictMorph.getState().nonce === expected) useDistrictMorph.getState().finishReturn();
  }, [popRoute]);

  useAnimatedReaction(() => progress.value, (value, previous) => {
    if (phase === 'morphing' && value >= .52 && (previous == null || previous < .52)) runOnJS(openRoute)(nonce);
    if (phase === 'returning' && value <= .77 && (previous == null || previous > .77)) runOnJS(popRoute)(nonce);
  }, [phase,nonce,openRoute,popRoute]);

  useEffect(() => {
    backdropOpacity.value = withTiming(areaMounted ? 0 : 1, {duration: reduced ? 0 : 160});
  }, [areaMounted,reduced,backdropOpacity]);

  useEffect(() => {
    if (phase === 'morphing' && entry) {
      navigationMade.current = false;
      backMade.current = false;
      opacity.value = 1;
      progress.value = 0;
      progress.value = withTiming(1, {
        duration: reduced ? 130 : 850,
        easing: Easing.bezier(.18,.72,.18,1),
      }, done => { if (done) runOnJS(finishOpen)(nonce); });
    } else if (phase === 'area-visible') {
      opacity.value = withTiming(0,{duration:reduced?0:130});
    } else if (phase === 'returning' && entry) {
      opacity.value = 1;
      progress.value = 1;
      progress.value = withTiming(0, {
        duration: reduced ? 130 : 760,
        easing: Easing.bezier(.42,0,.28,1),
      }, done => { if (done) runOnJS(finishReturn)(nonce); });
    } else if (phase === 'idle') {
      cancelAnimation(progress);
      progress.value = 0;
      opacity.value = 1;
    }
  }, [phase,entry,nonce,reduced,progress,opacity,finishOpen,finishReturn]);

  useEffect(() => {
    const subscription = AppState.addEventListener('change', state => {
      if (state === 'active') return;
      const current = useDistrictMorph.getState();
      if (current.phase === 'selecting') current.cancel(current.nonce);
      if (current.phase === 'morphing') {
        if (navigationMade.current) current.areaVisible(current.nonce);
        else current.cancel(current.nonce);
      }
      if (current.phase === 'returning') finishReturn(current.nonce);
    });
    return () => subscription.remove();
  }, [finishReturn]);

  const path = useAnimatedProps(() => ({
    d: entry ? interpolateRingPath(entry.source,entry.target,progress.value) : '',
  }), [entry]);
  const scrim = useAnimatedStyle(() => ({
    opacity: opacity.value * backdropOpacity.value * interpolate(progress.value,[0,.28,.76,1],[0,.04,.3,.35]),
  }));
  const surface = useAnimatedStyle(() => ({opacity: opacity.value}));
  const sourceCenter = entry ? entry.source.reduce((center,point) => [center[0]+point[0]/entry.source.length,center[1]+point[1]/entry.source.length] as [number,number],[0,0] as [number,number]) : [0,0];
  const label = useAnimatedStyle(() => ({
    opacity: opacity.value * interpolate(progress.value,[0,.15,.48,1],[0,0,.95,1]),
    left: interpolate(progress.value,[0,1],[sourceCenter[0]-70,24]),
    top: interpolate(progress.value,[0,1],[sourceCenter[1]-15,(viewport?.headerHeight ?? 235)-108]),
    transform:[{scale:interpolate(progress.value,[0,1],[.6,1])}],
  }), [sourceCenter[0],sourceCenter[1],viewport?.headerHeight]);
  const countStyle = useAnimatedStyle(() => ({
    opacity: opacity.value * interpolate(progress.value,[0,.25,.7,1],[0,0,.95,1]),
    left: interpolate(progress.value,[0,1],[sourceCenter[0]-30,26]),
    top: interpolate(progress.value,[0,1],[sourceCenter[1]+10,(viewport?.headerHeight ?? 235)-61]),
  }), [sourceCenter[0],sourceCenter[1],viewport?.headerHeight]);

  if (Platform.OS !== 'ios') return null;
  return <View ref={host} pointerEvents="none" accessibilityElementsHidden importantForAccessibility="no-hide-descendants"
    style={[StyleSheet.absoluteFillObject,{top:-insets.top,zIndex:100,elevation:100}]}
    onLayout={event => {
      const {width,height} = event.nativeEvent.layout;
      host.current?.measureInWindow((originX,originY) =>
        useDistrictMorph.getState().setViewport({width,height,originX,originY,headerHeight:Math.min(260,Math.max(224,height*.29))}));
    }}>
    {entry && (phase === 'morphing' || phase === 'returning' || phase === 'area-visible') && viewport && <>
      <Animated.View style={[StyleSheet.absoluteFillObject,{backgroundColor:colors.background},scrim]}/>
      <Animated.View style={[StyleSheet.absoluteFillObject,surface]}>
        <Svg width={viewport.width} height={viewport.height} pointerEvents="none">
          <AnimatedPath animatedProps={path} fill={DISTRICT_SURFACE}/>
        </Svg>
      </Animated.View>
      <Animated.Text numberOfLines={2} style={[{position:'absolute',maxWidth:viewport.width-48,color:colors.black,fontFamily:fonts.black,fontSize:30},label]}>{entry.name}</Animated.Text>
      <Animated.Text style={[{position:'absolute',color:colors.black,fontFamily:fonts.semibold,fontSize:13},countStyle]}>{entry.count} {entry.count===1?'event':'events'}</Animated.Text>
    </>}
  </View>;
}
