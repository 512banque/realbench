export type Fetcher<T> = (url: string, signal: AbortSignal) => Promise<T>;

/**
 * Launches `fetcher` on every URL in parallel and resolves with the value
 * from the first one to succeed. Rejects if every fetch rejects.
 *
 * Aborts every loser as soon as the winner is known.
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

  try {
    const winner = await Promise.any(promises);
    // Abort losers — winner already settled, abort is a no-op for it.
    for (const c of controllers) {
      if (!c.signal.aborted) c.abort();
    }
    return winner;
  } catch (e) {
    // All fetches failed — abort anything still pending defensively.
    for (const c of controllers) {
      if (!c.signal.aborted) c.abort();
    }
    throw e;
  }
}
