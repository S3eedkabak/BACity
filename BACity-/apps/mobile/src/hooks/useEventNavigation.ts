import { useCallback, useRef } from 'react';
import { router, useFocusEffect } from 'expo-router';
import { createNavigationGuard } from '../loading/navigation';
export function useEventNavigation() {
  const guard = useRef(createNavigationGuard());
  useFocusEffect(useCallback(() => { guard.current.reset(); }, []));
  return (id: string) => { if (guard.current.allow(Date.now())) router.push('/event/' + id); };
}
