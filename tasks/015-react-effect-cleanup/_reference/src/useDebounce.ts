import { useEffect, useState } from "react";

/**
 * Debounce a fast-changing value. Returns the value of `value` as it was
 * `delayMs` ago, but only after the value has been stable for that long.
 *
 * Cleanup clears the timer on every re-run (so rapid changes only fire
 * the last one) and on unmount (so we don't setState on a dead component).
 */
export function useDebounce<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const t = setTimeout(() => {
      setDebounced(value);
    }, delayMs);
    return () => clearTimeout(t);
  }, [value, delayMs]);

  return debounced;
}
