import { useSyncExternalStore } from "react";
import { AccessibilityInfo, AppState } from "react-native";
let reduced = true,
  inactive = false,
  revision = 0;
let subscription: { remove: () => void } | undefined,
  activity: { remove: () => void } | undefined;
const listeners = new Set<() => void>();
const notify = () => listeners.forEach((listener) => listener());
function publish(value: boolean) {
  if (value !== reduced) {
    reduced = value;
    notify();
  }
}
function subscribe(listener: () => void) {
  listeners.add(listener);
  if (!subscription) {
    const current = ++revision;
    let receivedEvent = false;
    inactive = !!AppState?.currentState && AppState.currentState !== "active";
    activity = AppState?.addEventListener("change", (state) => {
      const next = state !== "active";
      if (next !== inactive) {
        inactive = next;
        notify();
      }
    });
    subscription = AccessibilityInfo.addEventListener(
      "reduceMotionChanged",
      (value) => {
        receivedEvent = true;
        publish(value);
      },
    );
    void AccessibilityInfo.isReduceMotionEnabled()
      .then((value) => {
        if (revision === current && !receivedEvent) publish(value);
      })
      .catch(() => {});
  }
  return () => {
    listeners.delete(listener);
    if (!listeners.size) {
      subscription?.remove();
      activity?.remove();
      subscription = undefined;
      activity = undefined;
      revision++;
      reduced = true;
      inactive = false;
    }
  };
}
/** One shared OS preference/activity pair. Backgrounding stops ongoing motion. */
export function useMotionPreference() {
  return useSyncExternalStore(
    subscribe,
    () => reduced || inactive,
    () => true,
  );
}
