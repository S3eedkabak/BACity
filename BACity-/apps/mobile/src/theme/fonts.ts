import { foundations } from './foundations.ts';

/** Family aliases remain compatible; use fontStyles to apply an actual weight. */
export const fonts = { regular: foundations.font.family, medium: foundations.font.family, semibold: foundations.font.family, black: foundations.font.family, fallback: foundations.font.family } as const;
export const fontStyles = {
  regular: { fontFamily: fonts.regular, fontWeight: foundations.font.weights.regular },
  medium: { fontFamily: fonts.medium, fontWeight: foundations.font.weights.medium },
  semibold: { fontFamily: fonts.semibold, fontWeight: foundations.font.weights.semibold },
  black: { fontFamily: fonts.black, fontWeight: foundations.font.weights.black },
} as const;
export const fontSources = {} as const;
