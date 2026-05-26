`src/firstSuccessful.ts` fires N requests in parallel and returns the first one that responds,
but the losing requests keep running in the background (no abort). Fix it so it cancels the
losers via `AbortController.abort()` as soon as the winner is known. Do not modify the tests.
