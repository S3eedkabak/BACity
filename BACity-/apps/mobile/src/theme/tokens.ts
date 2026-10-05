import { colors } from './colors';

/** Semantic product primitives shared by core, social and premium contexts. */
export const tokens = {
  color: colors,
  space: { xs: 4, sm: 8, md: 12, lg: 20, xl: 28, xxl: 40, section: 48 },
  radius: { sm: 12, md: 20, lg: 28, hero: 36, pill: 999 },
  type: {
    display: { fontSize: 44, lineHeight: 48, fontWeight: '800' as const, letterSpacing: -1.8 },
    hero: { fontSize: 34, lineHeight: 38, fontWeight: '800' as const, letterSpacing: -1.2 },
    title: { fontSize: 26, lineHeight: 32, fontWeight: '700' as const, letterSpacing: -.7 },
    section: { fontSize: 22, lineHeight: 28, fontWeight: '700' as const, letterSpacing: -.5 },
    body: { fontSize: 16, lineHeight: 24, fontWeight: '400' as const },
    metadata: { fontSize: 13, lineHeight: 19, fontWeight: '500' as const },
    caption: { fontSize: 12, lineHeight: 17, fontWeight: '500' as const },
    action: { fontSize: 15, lineHeight: 20, fontWeight: '600' as const },
  },
  icon: { small: 18, standard: 24, feature: 32, touch: 48 },
  image: { hero: 1, feed: 1.45, rail: .9, compact: 1 },
  layout: { maxWidth: 760, gutter: 20, bottomInset: 104 },
  motion: { press: 120, transition: 240, sheet: 300, loadingReveal: 450 },
  scrim: 'rgba(24,21,31,.72)',
  premium: { background: '#191625', surface: '#292336', accent: '#FFB4A7', text: '#FFF8F4', muted: '#C6BDCF' },
} as const;
