// Rounded outward from the complete official 17-district geometry.
export const CITY_NORTH_EAST: [number, number] = [17.285, 48.266];
export const CITY_SOUTH_WEST: [number, number] = [16.945, 48.006];

// MapLibre native padding order: top, right, bottom, left.
export function cityOverviewPadding(topInset: number, bottomInset: number, previewHeight = 0): [number, number, number, number] {
  return [topInset + 76, 32, bottomInset + 88 + previewHeight, 32];
}

// Native uses an array; MapLibre GL JS expects named edge insets.
export function webCameraPadding(padding: number | [number, number] | [number, number, number, number]) {
  if (typeof padding === 'number') return padding;
  if (padding.length === 2) return {top: padding[0], right: padding[1], bottom: padding[0], left: padding[1]};
  return {top: padding[0], right: padding[1], bottom: padding[2], left: padding[3]};
}
