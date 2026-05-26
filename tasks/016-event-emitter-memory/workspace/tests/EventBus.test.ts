import { EventBus } from "../src/EventBus";

describe("EventBus — functional", () => {
  test("subscribe + emit invokes the handler", () => {
    const bus = new EventBus();
    const calls: unknown[] = [];
    bus.subscribe("hello", (p: string) => calls.push(p));

    bus.emit("hello", "world");

    expect(calls).toEqual(["world"]);
  });

  test("after unsubscribe, emit does not invoke the handler", () => {
    const bus = new EventBus();
    const calls: unknown[] = [];
    const unsub = bus.subscribe("hello", (p: string) => calls.push(p));

    bus.emit("hello", "first");
    unsub();
    bus.emit("hello", "second");

    expect(calls).toEqual(["first"]);
  });
});

describe("EventBus — listenerCount tracks correctly", () => {
  test("listenerCount reflects subscribe and unsubscribe", () => {
    const bus = new EventBus();
    expect(bus.listenerCount("e")).toBe(0);

    const unsub1 = bus.subscribe("e", () => {});
    const unsub2 = bus.subscribe("e", () => {});
    const unsub3 = bus.subscribe("e", () => {});
    expect(bus.listenerCount("e")).toBe(3);

    unsub2();
    expect(bus.listenerCount("e")).toBe(2);

    unsub1();
    unsub3();
    expect(bus.listenerCount("e")).toBe(0);
  });
});

describe("EventBus — no memory leak on heavy use", () => {
  test("10000 subscribe / unsubscribe pairs leave listenerCount at 0", () => {
    const bus = new EventBus();
    const unsubs: Array<() => void> = [];

    for (let i = 0; i < 10_000; i++) {
      // Distinct handler functions each time.
      unsubs.push(bus.subscribe("evt", () => {}));
    }

    expect(bus.listenerCount("evt")).toBe(10_000);

    for (const u of unsubs) u();

    expect(bus.listenerCount("evt")).toBe(0);

    // And emit triggers no handler — already covered by the no-call
    // semantics, but check anyway since this is the "no leak" headline.
    let invoked = 0;
    bus.subscribe("evt", () => {
      invoked++;
    });
    bus.emit("evt", undefined);
    expect(invoked).toBe(1);
  });

  test("interleaved subscribe/unsubscribe keeps listenerCount correct", () => {
    const bus = new EventBus();
    const unsubs: Array<() => void> = [];

    for (let i = 0; i < 1000; i++) {
      unsubs.push(bus.subscribe("x", () => {}));
      if (i % 3 === 0 && unsubs.length > 0) {
        const u = unsubs.shift()!;
        u();
      }
    }

    // After the loop the count must equal the number of still-live subs.
    expect(bus.listenerCount("x")).toBe(unsubs.length);

    // Tear down the rest.
    for (const u of unsubs) u();
    expect(bus.listenerCount("x")).toBe(0);
  });
});
