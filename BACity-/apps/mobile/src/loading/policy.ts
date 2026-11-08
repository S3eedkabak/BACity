export const LOADING_GRACE_MS = 500;
export const LOADING_EXIT_MS = 180;
export const LOADING_MIN_VISIBLE_MS = 200;
export function exitDelay(shownAt: number, now: number, minimumVisibleMs = LOADING_MIN_VISIBLE_MS) {
  return Math.max(0, minimumVisibleMs - (now - shownAt));
}
// Explicit opt-in for local development only. Never changes API transport/cache.
export function developmentDelay(enabled: boolean, value: string | undefined) {
  const ms = Number(value);
  return enabled && [500, 1500, 3000].includes(ms) ? ms : 0;
}
type Timer = ReturnType<typeof setTimeout>;
type Clock = { now: () => number; set: (callback: () => void, ms: number) => Timer; clear: (timer: Timer) => void };
// Browser timer functions must retain the global receiver (not Clock's `this`).
const systemClock: Clock = { now: () => Date.now(), set: (callback, ms) => setTimeout(callback, ms), clear: timer => clearTimeout(timer) };
/** Presentation alone is delayed; this controller never delays the operation/navigation. */
export class LoadingPresentation {
  private timers: Timer[] = [];
  private shownAt: number | undefined;
  private completed = false;
  private disposed = false;
  private show: () => void;
  private exit: () => void;
  private hide: () => void;
  private clock: Clock;
  private exitMs: number;
  private graceMs: number;
  private minimumVisibleMs: number;
  constructor(
    show: () => void,
    exit: () => void,
    hide: () => void,
    clock: Clock = systemClock,
    exitMs = LOADING_EXIT_MS,
    graceMs = LOADING_GRACE_MS,
    minimumVisibleMs = LOADING_MIN_VISIBLE_MS,
  ) {
    this.show = show; this.exit = exit; this.hide = hide; this.clock = clock; this.exitMs = exitMs;
    this.graceMs = graceMs; this.minimumVisibleMs = minimumVisibleMs;
  }
  start() {
    this.schedule(() => { this.shownAt = this.clock.now(); this.show(); }, this.graceMs);
  }
  complete() {
    if (this.completed || this.disposed) return;
    this.completed = true;
    this.clear();
    if (this.shownAt === undefined) return;
    const wait = exitDelay(this.shownAt, this.clock.now(), this.minimumVisibleMs);
    this.schedule(this.exit, wait);
    this.schedule(this.hide, wait + this.exitMs);
  }
  dispose() { this.disposed = true; this.clear(); }
  private schedule(callback: () => void, ms: number) { this.timers.push(this.clock.set(() => { if (!this.disposed) callback(); }, ms)); }
  private clear() { this.timers.forEach(timer => this.clock.clear(timer)); this.timers = []; }
}
