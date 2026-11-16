/** Controlled profiles: critically damped geometry, short press feedback. Times in ms. */
export const motion = {
  press: { duration: 100, scale: 0.98 },
  spring: { stiffness: 500, damping: 45, mass: 1, overshootClamping: true },
  surfaceSpring: { stiffness: 260, damping: 33, mass: 1, overshootClamping: true },
  badgeSpring: { stiffness: 420, damping: 42, mass: 1, overshootClamping: true },
  label: 300,
  icon: 150,
  check: 300,
  intent: 120,
  pop: [112, 158, 180] as const,
  burst: 550,
  bell: 420,
  hold: 1200,
  ringReset: 300,
  screen: 300,
  tab: 180,
  sheet: { stiffness: 300, damping: 35, mass: 1, overshootClamping: true },
} as const;
export function sheetTarget(
  position: number,
  velocity: number,
  detents: readonly number[],
) {
  "worklet";
  const projected = position + velocity * 0.18;
  return detents.reduce(
    (best, value) =>
      Math.abs(value - projected) < Math.abs(best - projected) ? value : best,
    detents[0],
  );
}
