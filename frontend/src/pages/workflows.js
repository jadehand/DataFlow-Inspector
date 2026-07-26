import { createPageController } from "./page-controller.js";

export const createWorkflowsPage = () => createPageController("workflow", context => {
  const root = document.getElementById("page-workflow");
  root.dataset.apiDomain = "catalog";
  const unsubscribe = context.store.subscribe(state => {
    if (state.activePage !== "workflow") return;
    root.dataset.project = state.projectId || "";
    root.dataset.mode = state.connectionMode;
  });
  return () => {
    unsubscribe();
    delete root.dataset.apiDomain;
  };
});
