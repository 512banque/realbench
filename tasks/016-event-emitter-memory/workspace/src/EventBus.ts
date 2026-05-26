export type Handler<P = unknown> = (payload: P) => void;
export type Unsubscribe = () => void;

/**
 * Typed event bus. `subscribe()` returns an `unsubscribe()` that is
 * supposed to remove the handler from the internal listener storage.
 *
 * BUG: rather than actually removing the handler from the listeners
 * Set, `unsubscribe` adds it to a side `tombstones` Set. `emit()`
 * checks the tombstone Set and skips those handlers, so from the
 * outside the handler does stop firing after unsubscribe. But:
 *   1. The handlers Set never shrinks → `listenerCount()` lies.
 *   2. Memory grows on every subscribe / unsubscribe pair → leak.
 *
 * The bug is invisible from a single subscribe → emit → unsubscribe →
 * emit smoke test, but a stress test that subscribes and unsubscribes
 * N times shows the listeners Map ballooning.
 */
export class EventBus<E extends string = string> {
  private listeners: Map<E, Set<Handler<any>>> = new Map();
  private tombstones: Map<E, Set<Handler<any>>> = new Map();

  subscribe<P = unknown>(event: E, handler: Handler<P>): Unsubscribe {
    let set = this.listeners.get(event);
    if (!set) {
      set = new Set();
      this.listeners.set(event, set);
    }
    set.add(handler as Handler<any>);

    return () => {
      let t = this.tombstones.get(event);
      if (!t) {
        t = new Set();
        this.tombstones.set(event, t);
      }
      // BUG: marks the handler as removed instead of actually deleting it.
      t.add(handler as Handler<any>);
    };
  }

  emit<P = unknown>(event: E, payload: P): void {
    const set = this.listeners.get(event);
    if (!set) return;
    const tomb = this.tombstones.get(event);
    for (const h of Array.from(set)) {
      if (tomb && tomb.has(h)) continue;
      h(payload);
    }
  }

  listenerCount(event: E): number {
    const set = this.listeners.get(event);
    return set ? set.size : 0;
  }
}
