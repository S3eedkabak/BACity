/** Ignore duplicate pushes, not navigation itself. Resets on originating-screen focus. */
export function createNavigationGuard() {
  let last = -Infinity;
  return { reset: () => { last = -Infinity; }, allow: (now: number) => {
    if (now - last < 700) return false;
    last = now; return true;
  } };
}
