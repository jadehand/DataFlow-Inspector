import { createPageController } from "./page-controller.js";

export const createOverviewPage = () => createPageController("overview", context => {
  const root = document.getElementById("page-overview");
  root.dataset.apiDomain = "projects";
  const unsubscribe = context.store.subscribe(state => {
    if (state.activePage !== "overview") return;
    root.dataset.project = state.projectId || "";
    root.dataset.mode = state.connectionMode;
  });
  return () => {
    unsubscribe();
    delete root.dataset.apiDomain;
  };
});
