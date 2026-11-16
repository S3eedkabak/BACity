import { foundations } from './foundations.ts';

type Palette = { [Key in keyof typeof foundations.palettes.dark]: string };
export const darkColors: Palette = foundations.palettes.dark;
export const lightColors: Palette = foundations.palettes.light;
// primaryDark is the compatible readable-accent alias; onBrand/onMedia stay light in both modes.
let mode: 'light' | 'dark' = 'dark';
export function setColorMode(next: 'light' | 'dark') { mode = next; }
export function getColorMode() { return mode; }
/** Backward-compatible semantic palette. No copied style stores a stale mode. */
export const colors: typeof darkColors = new Proxy(darkColors, {
  get(_target, key) { return (mode === 'light' ? lightColors : darkColors)[key as keyof typeof darkColors]; },
});
