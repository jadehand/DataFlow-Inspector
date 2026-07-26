export function createEventScope() {
  const cleanups = [];

  return {
    assign(element, property, handler) {
      if (!element) return;
      const previous = element[property];
      element[property] = handler;
      cleanups.push(() => {
        if (element[property] === handler) element[property] = previous || null;
      });
    },
    listen(element, type, handler, options) {
      if (!element) return;
      element.addEventListener(type, handler, options);
      cleanups.push(() => element.removeEventListener(type, handler, options));
    },
    cleanup() {
      cleanups.splice(0).reverse().forEach(dispose => dispose());
    }
  };
}
