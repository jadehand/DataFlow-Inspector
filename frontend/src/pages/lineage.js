import { createPageController } from "./page-controller.js";

export const createLineagePage = () => createPageController("lineage", context => {
  const root = document.getElementById("page-lineage");
  root.dataset.apiDomain = "lineage";
  const unsubscribe = context.store.subscribe(state => {
    if (state.activePage !== "lineage") return;
    root.dataset.project = state.projectId || "";
    root.dataset.focus = state.focus || "";
  });
  return () => {
    unsubscribe();
    delete root.dataset.apiDomain;
  };
});
