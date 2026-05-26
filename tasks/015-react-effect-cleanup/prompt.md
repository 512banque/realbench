The `useDebounce` hook in `src/useDebounce.ts` leaks its timers: every change to
`value` creates a new `setTimeout` without canceling the previous one, and a setTimeout
remains pending after unmount. Fix it to properly clean up the timers via the return
value of `useEffect`. Do not modify the tests.
