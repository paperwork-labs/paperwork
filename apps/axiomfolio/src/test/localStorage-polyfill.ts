/**
 * Node 25+ can expose experimental `globalThis.localStorage` without a working `getItem`,
 * which breaks Vitest + jsdom/happy-dom (ColorModeProvider, tests using localStorage).
 * Must load before any other setup (see vite.config.ts setupFiles order).
 */
(function polyfillLocalStorage(): void {
  function memoryStorage(): Storage {
    const store = new Map<string, string>();
    return {
      get length() {
        return store.size;
      },
      clear: () => {
        store.clear();
      },
      getItem: (key: string) => (store.has(key) ? store.get(key)! : null),
      key: (index: number) => {
        const keys = [...store.keys()];
        return index >= 0 && index < keys.length ? keys[index]! : null;
      },
      removeItem: (key: string) => {
        store.delete(key);
      },
      setItem: (key: string, value: string) => {
        store.set(key, String(value));
      },
    };
  }

  function broken(ls: Storage | undefined | null): boolean {
    return ls == null || typeof ls.getItem !== 'function';
  }

  const shared = memoryStorage();
  const g = globalThis as typeof globalThis & { localStorage?: Storage };

  if (broken(g.localStorage)) {
    Object.defineProperty(g, 'localStorage', {
      value: shared,
      writable: true,
      configurable: true,
    });
  }

  if (typeof window !== 'undefined' && broken(window.localStorage)) {
    Object.defineProperty(window, 'localStorage', {
      value: shared,
      writable: true,
      configurable: true,
    });
  }
})();
