import { useSyncExternalStore } from 'react';
import { useReducedMotion } from 'motion/react';

export function useMedia(query: string): boolean {
  return useSyncExternalStore(
    (cb) => { const m = matchMedia(query); m.addEventListener('change', cb); return () => m.removeEventListener('change', cb); },
    () => matchMedia(query).matches,
  );
}

/** True unless the visitor prefers reduced motion. */
export function useMotionOK(): boolean {
  return !useReducedMotion();
}

/** Pinned, scroll-driven stories need a wide and tall enough viewport, and motion allowed. Otherwise sections stack. */
export function usePinned(): boolean {
  const roomy = useMedia('(min-width: 1000px) and (min-height: 620px)');
  return useMotionOK() && roomy;
}
