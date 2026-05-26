export type Fetcher<T> = (url: string, signal: AbortSignal) => Promise<T>;

/**
 * Launches `fetcher` on every URL in parallel and resolves with the value
 * from the first one to succeed. Rejects if every fetch rejects.
 *
 * BUG: when the winner resolves, the other in-flight fetches are not
 * aborted — they keep running in the background, hold the event loop
 * open and (in real life) keep consuming network. Loser fetches must
 * receive an `abort()` on their AbortController as soon as the winner
 * is known.
 */
export async function firstSuccessful<T>(
  urls: string[],
  fetcher: Fetcher<T>,
): Promise<T> {
  if (urls.length === 0) {
    throw new Error("firstSuccessful: empty url list");
  }

  const controllers = urls.map(() => new AbortController());
  const promises = urls.map((url, i) => fetcher(url, controllers[i].signal));

  // BUG: returns the first settled promise but never aborts the losers.
  return Promise.any(promises);
}
