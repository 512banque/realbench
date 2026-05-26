import { useEffect, useState } from "react";

/**
 * Debounce a fast-changing value. Returns the value of `value` as it was
 * `delayMs` ago, but only after the value has been stable for that long.
 *
 * BUG: the effect schedules a `setTimeout` but never cleans it up. As a
 * result:
 *   1. Rapid changes to `value` queue multiple timers, all of which fire.
 *   2. Unmounting the component leaves a pending timer that will still
 *      try to setState on a dead component.
 */
export function useDebounce<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    // BUG: no cleanup function returned.
    setTimeout(() => {
      setDebounced(value);
    }, delayMs);
  }, [value, delayMs]);

  return debounced;
}
