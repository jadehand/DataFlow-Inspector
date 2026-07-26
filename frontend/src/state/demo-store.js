import { deepClone, deepFreeze } from "./store.js";

export function createDemoStore(seed) {
  const original = deepFreeze(deepClone(seed || {}));
  let snapshot = original;

  return {
    getSnapshot: () => deepClone(snapshot),
    reset() {
      snapshot = original;
      return this.getSnapshot();
    }
  };
}
