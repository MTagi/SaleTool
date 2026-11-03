import { useCallback, useMemo, useState } from "react";

/**
 * A selection set with the common operations used to manage it.
 *
 * All four pages need the same operations — toggle a row, select all, clear all,
 * and check whether a row is selected. Each page used to implement them
 * differently: some used `Set`, some used arrays, and some put toggle functions
 * inside JSX. Keep them here so every page has the same behavior and interface.
 *
 * The caller chooses item keys (company name, list index, etc.); this hook makes
 * no assumptions about their type, as long as they can be compared with `===`.
 */
export function useSelection(initial = []) {
  const [keys, setKeys] = useState(() => new Set(initial));

  const toggle = useCallback((key) => {
    setKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  /** Select all or clear all. Pass `allKeys` when called because the list follows the data. */
  const setAll = useCallback((on, allKeys) => {
    setKeys(on ? new Set(allKeys) : new Set());
  }, []);

  const replace = useCallback((nextKeys) => setKeys(new Set(nextKeys)), []);
  const clear = useCallback(() => setKeys(new Set()), []);

  return useMemo(
    () => ({
      keys,
      size: keys.size,
      isEmpty: keys.size === 0,
      has: (key) => keys.has(key),
      /** Is the entire list selected? Used by the "select all" checkbox. */
      hasAll: (allKeys) => allKeys.length > 0 && allKeys.every((key) => keys.has(key)),
      toList: () => [...keys],
      toggle,
      setAll,
      replace,
      clear,
    }),
    [keys, toggle, setAll, replace, clear],
  );
}
