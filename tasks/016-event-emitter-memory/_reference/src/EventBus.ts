export type Handler<P = unknown> = (payload: P) => void;
export type Unsubscribe = () => void;

/**
 * Typed event bus. `subscribe()` returns an `unsubscribe()` that removes
 * the handler from the listener list.
 *
 * Implementation: handlers per event are stored in a Set keyed by
 * reference, so `set.delete(handler)` is O(1) and unambiguous.
 */
export class EventBus<E extends string = string> {
  private listeners: Map<E, Set<Handler<any>>> = new Map();

  subscribe<P = unknown>(event: E, handler: Handler<P>): Unsubscribe {
    let set = this.listeners.get(event);
    if (!set) {
      set = new Set();
      this.listeners.set(event, set);
    }
    set.add(handler as Handler<any>);

    return () => {
      const s = this.listeners.get(event);
      if (!s) return;
      s.delete(handler as Handler<any>);
      if (s.size === 0) this.listeners.delete(event);
    };
  }

  emit<P = unknown>(event: E, payload: P): void {
    const set = this.listeners.get(event);
    if (!set) return;
    // Iterate over a snapshot so unsubscribes during emit don't break iteration.
    for (const h of Array.from(set)) {
      h(payload);
    }
  }

  listenerCount(event: E): number {
    const set = this.listeners.get(event);
    return set ? set.size : 0;
  }
}
