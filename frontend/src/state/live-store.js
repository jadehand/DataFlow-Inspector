import { deepClone, deepFreeze } from "./store.js";

export function createLiveStore() {
  let snapshot = deepFreeze({
    projects: [],
    versions: [],
    tables: [],
    metrics: [],
    lineage: { nodes: [], edges: [] },
    workflows: [],
    findings: []
  });

  return {
    getSnapshot: () => snapshot,
    replace(patch) {
      snapshot = deepFreeze({ ...deepClone(snapshot), ...deepClone(patch || {}) });
      return snapshot;
    },
    clear() {
      snapshot = deepFreeze({
        projects: [], versions: [], tables: [], metrics: [],
        lineage: { nodes: [], edges: [] }, workflows: [], findings: []
      });
      return snapshot;
    }
  };
}
