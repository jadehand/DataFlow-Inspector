const ROUTE_KEYS = ["page", "project", "table", "left", "right", "focus"];
const DEFAULT_PAGE = "overview";

export function readRoute(locationObject = window.location) {
  const params = new URLSearchParams(locationObject.search);
  return {
    activePage: params.get("page") || DEFAULT_PAGE,
    projectId: params.get("project"),
    table: params.get("table"),
    leftVersion: params.get("left"),
    rightVersion: params.get("right"),
    focus: params.get("focus")
  };
}

export function createRouter({ store, windowObject = window }) {
  function hrefFor(patch) {
    const url = new URL(windowObject.location.href);
    const state = { ...store.getState(), ...(patch || {}) };
    const values = {
      page: state.activePage,
      project: state.projectId,
      table: state.table,
      left: state.leftVersion,
      right: state.rightVersion,
      focus: state.focus
    };
    ROUTE_KEYS.forEach(key => {
      const value = values[key];
      if (value == null || value === "" || (key === "page" && value === DEFAULT_PAGE)) {
        url.searchParams.delete(key);
      } else {
        url.searchParams.set(key, value);
      }
    });
    return url;
  }

  function commit(patch, { replace = false } = {}) {
    store.setState(patch);
    const url = hrefFor();
    windowObject.history[replace ? "replaceState" : "pushState"]({}, "", url);
  }

  const onPopState = () => store.setState(readRoute(windowObject.location));
  windowObject.addEventListener("popstate", onPopState);

  return {
    start() {
      store.setState(readRoute(windowObject.location));
      commit({}, { replace: true });
    },
    navigate(page, patch = {}) {
      commit({ ...patch, activePage: page });
    },
    update(patch, options) {
      commit(patch, options);
    },
    destroy() {
      windowObject.removeEventListener("popstate", onPopState);
    }
  };
}
