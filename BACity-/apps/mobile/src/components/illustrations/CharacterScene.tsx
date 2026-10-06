import { useEffect } from 'react';
import { StyleSheet, View } from 'react-native';
import Svg, { Circle, Ellipse, G, Path, Rect } from 'react-native-svg';
import Animated, { cancelAnimation, useAnimatedStyle, useReducedMotion, useSharedValue, withRepeat, withTiming } from 'react-native-reanimated';
import { colors } from '../../theme/colors';
import { tokens } from '../../theme/tokens';

export type CharacterMood = 'intro' | 'waiting' | 'ready' | 'error' | 'saved' | 'search' | 'city';
/** Editable vector DEVELOPMENT artwork, not the final authored character film.
 * One state adapter can later host a Rive artboard without changing app readiness.
 * A bounded SVG tree replaces raster frames and independently animated RN limbs.
 */
export function CharacterScene({ mood = 'ready', size = 240 }: { mood?: CharacterMood; size?: number }) {
  const reduced = useReducedMotion();
  const breath = useSharedValue(0);
  useEffect(() => {
    breath.value = 0;
    if (!reduced && mood === 'waiting') breath.value = withRepeat(withTiming(1, { duration: 1800 }), -1, true);
    return () => cancelAnimation(breath);
  }, [mood, reduced, breath]);
  const idle = useAnimatedStyle(() => ({ transform: [{ translateY: breath.value * -2 }] }));
  const ready = ['ready', 'saved', 'city'].includes(mood);
  return <View style={{ width: size, height: size }} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
    <Animated.View style={[StyleSheet.absoluteFill, idle]}>
      <Svg width="100%" height="100%" viewBox="0 0 280 280">
        <Rect x="27" y="35" width="218" height="219" rx="38" fill={colors.surface} />
        <Rect x="168" y="56" width="51" height="106" rx="24" fill={colors.surfaceAlt} stroke={colors.border} strokeWidth="2" />
        <Path d="M177 69L208 100M177 110L209 142" stroke={colors.border} strokeWidth="2" />
        <Ellipse cx="130" cy="252" rx="74" ry="7" fill={colors.black} />
        <G>
          <Path d="M110 171L102 238L120 238L137 185L146 238L165 238L160 171Z" fill="#53535F" />
          <Path d="M100 235L119 235L123 252L89 252Q86 244 100 235M146 235L165 235L181 249Q181 254 149 252Z" fill={colors.text} />
          <Path d="M98 95Q128 86 155 97L172 175Q132 188 92 173Z" fill={mood === 'intro' ? colors.surfaceAlt : colors.primary} />
          <Path d="M131 99L130 175M99 148L119 150M144 150L162 147" stroke={colors.primaryDark} strokeWidth="2.5" fill="none" />
          <Path d="M98 99Q81 105 77 149Q77 162 97 167L108 154L92 146L105 113M153 101Q173 106 181 127L167 137L149 116" fill={colors.primary} />
          <Path d="M97 159L107 151L116 155Q121 167 111 173L101 170M165 130L174 121L188 115Q198 122 188 135L179 140Z" fill="#CC977E" />
          <Rect x="117" y="74" width="24" height="24" rx="9" fill="#CC977E" />
          <Path d="M107 53Q105 33 131 30Q153 31 154 54L149 78Q143 91 126 88Q109 83 107 53Z" fill="#DCA58B" />
          <Path d="M105 62Q91 36 109 28Q126 13 148 29Q169 37 151 63L146 44Q117 50 110 38L110 62Z" fill="#252028" />
          <Path d="M118 57L124 55M137 55L144 57" stroke="#252028" strokeWidth="2.5" strokeLinecap="round" />
          <Circle cx="121" cy="62" r="2" fill="#252028" /><Circle cx="139" cy="62" r="2" fill="#252028" />
          <Path d={mood === 'error' ? 'M123 79Q130 73 138 79' : ready ? 'M123 75Q131 85 139 75' : 'M125 77L135 77'} fill="none" stroke="#6B393F" strokeWidth="2" strokeLinecap="round" />
        </G>
        <G>
          <Rect x="177" y="100" width="20" height="35" rx="4" fill={colors.black} stroke={colors.border} strokeWidth="2" />
          <Rect x="181" y="105" width="12" height="22" rx="2" fill={ready ? colors.primaryDark : colors.surfaceAlt} />
          {ready && <Path d="M184 116L187 119L191 111" stroke={colors.black} strokeWidth="1.5" fill="none" />}
          {mood !== 'intro' && <G><Circle cx="100" cy="170" r="5" fill="none" stroke={colors.warning} strokeWidth="3" /><Path d="M100 175L100 190L106 190M100 184L105 184" stroke={colors.warning} strokeWidth="3" /></G>}
        </G>
        {mood === 'saved' && <G><Rect x="37" y="142" width="38" height="57" rx="6" fill={colors.primarySoft} stroke={colors.primaryDark} /><Path d="M47 154H65M47 162H65M47 181H58" stroke={colors.primaryDark} strokeWidth="2" /></G>}
        {mood === 'search' && <G><Circle cx="65" cy="174" r="17" fill="none" stroke={colors.primaryDark} strokeWidth="4" /><Path d="M53 189L42 203" stroke={colors.primaryDark} strokeWidth="5" /></G>}
        {mood === 'city' && <Path d="M38 126V90H52V75H68V108H81V126" fill={colors.primarySoft} stroke={colors.primaryDark} strokeWidth="1.5" />}
      </Svg>
    </Animated.View>
  </View>;
}
