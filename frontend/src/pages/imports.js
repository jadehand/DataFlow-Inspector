import { createPageController } from "./page-controller.js";

export const createImportsPage = () => createPageController("imports", context => {
  const root = document.getElementById("page-imports");
  root.dataset.apiDomain = "imports";
  const unsubscribe = context.store.subscribe(state => {
    if (state.activePage !== "imports") return;
    root.dataset.project = state.projectId || "";
    root.dataset.mode = state.connectionMode;
  });
  return () => {
    unsubscribe();
    delete root.dataset.apiDomain;
  };
});
