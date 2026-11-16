import { foundations } from '../theme/foundations.ts';

/** One canonical owner, with purpose-specific profiles rather than one universal duration. */
export const motion = foundations.interactionMotion;
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
