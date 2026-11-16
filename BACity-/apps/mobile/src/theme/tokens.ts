import { colors } from './colors';
import { foundations } from './foundations.ts';

/** Compatible native adapter; dynamic palette getters preserve appearance changes. */
export const tokens = {
  color: colors,
  accessibility: foundations.accessibility,
  space: foundations.space,
  radius: foundations.radius,
  type: foundations.type,
  icon: foundations.icon,
  image: foundations.image,
  layout: foundations.layout,
  motion: foundations.motion,
  opacity: foundations.opacity,
  elevation: foundations.elevation,
  border: foundations.border,
  get scrim() { return colors.overlay; },
  premium: { get background() { return colors.background; }, get surface() { return colors.surfaceAlt; }, get accent() { return colors.primaryDark; }, get text() { return colors.text; }, get muted() { return colors.textMuted; } },
} as const;
