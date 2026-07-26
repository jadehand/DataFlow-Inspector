export function createInitialState() {
  return {
    activePage: "overview",
    connectionMode: "connecting",
    projectId: null,
    table: null,
    leftVersion: null,
    rightVersion: null,
    focus: null,
    projects: [],
    versions: [],
    selectedAssets: [],
    impactSeed: null,
    requestGeneration: 0
  };
}

export function deepClone(value) {
  return value == null ? value : structuredClone(value);
}

export function deepFreeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) return value;
  Reflect.ownKeys(value).forEach(key => deepFreeze(value[key]));
  return Object.freeze(value);
}

export function createStore(initialState) {
  let state = deepFreeze(deepClone(initialState || {}));
  const listeners = new Set();

  return {
    getState() {
      return state;
    },
    setState(patch) {
      const next = deepFreeze({ ...deepClone(state), ...deepClone(patch || {}) });
      if (Object.keys(next).every(key => Object.is(next[key], state[key]))) return;
      const previous = state;
      state = next;
      listeners.forEach(listener => listener(state, previous));
    },
    resetProject(projectId) {
      const requestGeneration = Number(state.requestGeneration || 0) + 1;
      this.setState({
        projectId,
        table: null,
        leftVersion: null,
        rightVersion: null,
        focus: null,
        versions: [],
        selectedAssets: [],
        impactSeed: null,
        requestGeneration
      });
      return requestGeneration;
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    }
  };
}
