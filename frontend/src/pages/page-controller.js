export function createPageController(page, setup = () => {}) {
  let cleanup = () => {};
  return {
    page,
    mount(context) {
      cleanup();
      cleanup = setup(context) || (() => {});
    },
    unmount() {
      cleanup();
      cleanup = () => {};
    }
  };
}

export function mountRoutePage(context, page, onEnter = () => {}) {
  let active = false;
  const apply = state => {
    const nextActive = state.activePage === page;
    if (nextActive && (!active || state)) onEnter(state);
    active = nextActive;
  };
  apply(context.store.getState());
  return context.store.subscribe(apply);
}
