import { useCallback, useEffect, useRef, useState } from 'react';
/** Native refresh controls represent a pull gesture, never a background query. */
export function usePullRefresh(action: () => Promise<unknown>) {
  const [refreshing, setRefreshing] = useState(false);
  const latest = useRef(action), running = useRef<Promise<unknown> | null>(null), mounted = useRef(true);
  latest.current = action;
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const onRefresh = useCallback(() => {
    if (running.current) return running.current;
    setRefreshing(true);
    running.current = Promise.resolve().then(() => latest.current()).finally(() => {
      running.current = null;
      if (mounted.current) setRefreshing(false);
    });
    return running.current;
  }, []);
  return { refreshing, onRefresh };
}
