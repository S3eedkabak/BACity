export const darkColors = {
  background: "#100E12",
  surface: "#1C191F",
  surfaceAlt: "#28232C",
  border: "#3A333F",
  text: "#F6F1F3",
  textMuted: "#B7ADB9",
  primary: "#A93468",
  // Legacy name retained for callers; on dark surfaces this is the readable accent.
  primaryDark: "#E69ABB",
  primarySoft: "#35202D",
  accent: "#CF7EA5",
  free: "#96CBB0",
  danger: "#EFA0AD",
  white: "#FFF8FB",
  black: "#100E12",
  shadow: "#000000",
  mapWater: "#182E38",
  textInverse: "#100E12",
  dangerSurface: "#422330",
  successSurface: "#20392E",
  warning: "#DBC092",
  overlay: "rgba(10,8,12,.78)",
  mediaOverlay: "rgba(16,14,18,.86)",
  skeleton: "#332D37",
  mapLand: "#211F27",
  mapPark: "#25352D",
  mapRoad: "#544A58",
};

export const lightColors: typeof darkColors = {
  ...darkColors,
  background: '#FFF8FB', surface: '#FFFFFF', surfaceAlt: '#F4EAF0', border: '#D9C7D1',
  text: '#24141E', textMuted: '#6F5664', primaryDark: '#8B2452', primarySoft: '#F7E4EE',
  accent: '#8B2452', free: '#285D42', danger: '#9B263E', textInverse: '#FFF8FB',
  dangerSurface: '#FCE7ED', successSurface: '#E5F2EB', warning: '#725317', skeleton: '#E6D6DF',
  mediaOverlay: 'rgba(255,248,251,.94)', mapWater: '#D0E6ED', mapLand: '#F6EEF2', mapPark: '#DCEBDD', mapRoad: '#B7A7B0',
};
let mode: 'light' | 'dark' = 'dark';
export function setColorMode(next: 'light' | 'dark') { mode = next; }
export function getColorMode() { return mode; }
/** Backward-compatible semantic palette. No copied style stores a stale mode. */
export const colors: typeof darkColors = new Proxy(darkColors, {
  get(_target, key) { return (mode === 'light' ? lightColors : darkColors)[key as keyof typeof darkColors]; },
});
