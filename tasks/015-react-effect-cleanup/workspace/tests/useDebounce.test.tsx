import React, { useEffect, useRef } from "react";
import { act, render } from "@testing-library/react";
import { useDebounce } from "../src/useDebounce";

beforeEach(() => {
  jest.useFakeTimers();
});

afterEach(() => {
  act(() => {
    jest.runOnlyPendingTimers();
  });
  jest.useRealTimers();
});

function Probe({ value, delay }: { value: string; delay: number }) {
  const debounced = useDebounce(value, delay);
  return <span data-testid="out">{debounced}</span>;
}

/** Component that records every distinct debounced value it has ever shown. */
function Recorder({
  value,
  delay,
  log,
}: {
  value: string;
  delay: number;
  log: string[];
}) {
  const debounced = useDebounce(value, delay);
  const last = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (last.current !== debounced) {
      log.push(debounced);
      last.current = debounced;
    }
  });
  return <span data-testid="out">{debounced}</span>;
}

describe("useDebounce — functional", () => {
  test("returns the new value after the delay", () => {
    const { rerender, getByTestId } = render(
      <Probe value="a" delay={100} />,
    );

    expect(getByTestId("out").textContent).toBe("a");

    rerender(<Probe value="b" delay={100} />);
    // Before delay completes the old value is still visible.
    expect(getByTestId("out").textContent).toBe("a");

    act(() => {
      jest.advanceTimersByTime(100);
    });

    expect(getByTestId("out").textContent).toBe("b");
  });
});

describe("useDebounce — no timer leak", () => {
  test("rapid changes never queue more than one timer at a time", () => {
    const { rerender } = render(<Probe value="v0" delay={100} />);

    // Initial mount queued one timer for "v0" → "v0".
    // After every rerender, exactly one timer should be pending: the
    // latest one. In the buggy implementation, each rerender adds a
    // timer without canceling the previous, so the count grows.
    const peaks: number[] = [];
    for (let i = 1; i <= 10; i++) {
      rerender(<Probe value={`v${i}`} delay={100} />);
      act(() => {
        jest.advanceTimersByTime(1);
      });
      peaks.push(jest.getTimerCount());
    }

    // With proper cleanup we expect at most 1 pending timer after each
    // rerender. The buggy version accumulates → at least 5 by the end.
    const maxPeak = Math.max(...peaks);
    expect(maxPeak).toBeLessThanOrEqual(1);
  });

  test("rapid changes only deliver the final value (no intermediate firings)", () => {
    const log: string[] = [];
    const { rerender } = render(<Recorder value="v0" delay={100} log={log} />);

    // 10 rapid changes, 1ms apart. None should reach `debounced` before
    // the delay elapses.
    for (let i = 1; i <= 10; i++) {
      rerender(<Recorder value={`v${i}`} delay={100} log={log} />);
      act(() => {
        jest.advanceTimersByTime(1);
      });
    }

    // Drain.
    act(() => {
      jest.advanceTimersByTime(500);
    });

    // The recorder should have logged at most two distinct values:
    // the initial "v0" and the final "v10". In the buggy version we
    // see every intermediate value because every timer fires.
    // Filter consecutive duplicates is unnecessary — `last.current`
    // already deduplicates.
    expect(log[0]).toBe("v0");
    expect(log[log.length - 1]).toBe("v10");
    expect(log.length).toBeLessThanOrEqual(2);
  });

  test("unmount leaves no pending timer", () => {
    const { rerender, unmount } = render(<Probe value="a" delay={100} />);
    rerender(<Probe value="b" delay={100} />);

    // Timer is pending — unmount before it fires.
    unmount();

    // After unmount, in the reference impl the cleanup runs and the
    // pending timer is cleared. In the buggy impl it's left dangling.
    expect(jest.getTimerCount()).toBe(0);
  });

  test("stress: 100 rapid changes never accumulate timers", () => {
    const { rerender } = render(<Probe value="v0" delay={50} />);

    let maxCount = 0;
    for (let i = 1; i <= 100; i++) {
      rerender(<Probe value={`v${i}`} delay={50} />);
      act(() => {
        jest.advanceTimersByTime(1);
      });
      const c = jest.getTimerCount();
      if (c > maxCount) maxCount = c;
    }

    // Reference impl: exactly 1 pending timer at any time.
    // Buggy impl: grows to ~50 (until first ones start firing).
    expect(maxCount).toBeLessThanOrEqual(1);
  });
});
