import { firstSuccessful, Fetcher } from "../src/firstSuccessful";

/**
 * Build a fetcher whose URL → delay map is given. The fetcher resolves
 * with the URL after `delay` ms, unless the AbortSignal fires first, in
 * which case it rejects with an AbortError.
 *
 * Tracks, per URL:
 *  - whether it was started
 *  - whether the signal was aborted before it resolved
 *  - whether the response actually resolved (delay completed without abort)
 */
function makeFetcher(delays: Record<string, number>) {
  const stats: Record<
    string,
    { started: boolean; aborted: boolean; resolved: boolean }
  > = {};

  for (const url of Object.keys(delays)) {
    stats[url] = { started: false, aborted: false, resolved: false };
  }

  const fetcher: Fetcher<string> = (url, signal) => {
    stats[url] = stats[url] || { started: false, aborted: false, resolved: false };
    stats[url].started = true;

    return new Promise<string>((resolve, reject) => {
      const delay = delays[url] ?? 50;

      const onAbort = () => {
        stats[url].aborted = true;
        clearTimeout(t);
        const err = new Error("aborted");
        err.name = "AbortError";
        reject(err);
      };

      if (signal.aborted) {
        onAbort();
        return;
      }

      const t = setTimeout(() => {
        stats[url].resolved = true;
        signal.removeEventListener("abort", onAbort);
        resolve(url);
      }, delay);

      signal.addEventListener("abort", onAbort, { once: true });
    });
  };

  return { fetcher, stats };
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

describe("firstSuccessful — functional", () => {
  test("returns the value of the first fetch to succeed", async () => {
    const { fetcher } = makeFetcher({
      "a": 50,
      "b": 10, // fastest
      "c": 100,
    });

    const result = await firstSuccessful(["a", "b", "c"], fetcher);
    expect(result).toBe("b");
  });

  test("rejects if every fetch rejects", async () => {
    const rejecting: Fetcher<string> = () =>
      Promise.reject(new Error("boom"));

    await expect(firstSuccessful(["a", "b"], rejecting)).rejects.toBeDefined();
  });
});

describe("firstSuccessful — abort losers", () => {
  test("aborts all losers once the winner resolves", async () => {
    const { fetcher, stats } = makeFetcher({
      "u1": 10, // winner
      "u2": 100,
      "u3": 200,
      "u4": 300,
      "u5": 400,
    });

    const winner = await firstSuccessful(
      ["u1", "u2", "u3", "u4", "u5"],
      fetcher,
    );
    expect(winner).toBe("u1");

    // Give the event loop a tick to deliver abort events.
    await sleep(50);

    // Losers must all have been aborted.
    expect(stats["u2"].aborted).toBe(true);
    expect(stats["u3"].aborted).toBe(true);
    expect(stats["u4"].aborted).toBe(true);
    expect(stats["u5"].aborted).toBe(true);

    // And the losers must NOT have been allowed to resolve.
    expect(stats["u2"].resolved).toBe(false);
    expect(stats["u3"].resolved).toBe(false);
    expect(stats["u4"].resolved).toBe(false);
    expect(stats["u5"].resolved).toBe(false);
  });

  test("no leak under stress: 200 iterations × 4 fetches, zero unaborted losers", async () => {
    let totalLeaked = 0;

    for (let i = 0; i < 200; i++) {
      const { fetcher, stats } = makeFetcher({
        [`winner_${i}`]: 1, // fastest by far
        [`l1_${i}`]: 80,
        [`l2_${i}`]: 120,
        [`l3_${i}`]: 160,
      });

      const winner = await firstSuccessful(
        [`winner_${i}`, `l1_${i}`, `l2_${i}`, `l3_${i}`],
        fetcher,
      );
      expect(winner).toBe(`winner_${i}`);

      // Tiny pause to let abort propagate
      await sleep(5);

      // Count losers that were allowed to keep running (started, not aborted)
      for (const url of [`l1_${i}`, `l2_${i}`, `l3_${i}`]) {
        if (stats[url].started && !stats[url].aborted) {
          totalLeaked++;
        }
      }
    }

    expect(totalLeaked).toBe(0);
  }, 60000);
});
