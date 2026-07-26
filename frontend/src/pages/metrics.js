import { createPageController } from "./page-controller.js";

export const createMetricsPage = () => createPageController("metrics", context => {
  const root = document.getElementById("page-metrics");
  root.dataset.apiDomain = "catalog";
  const unsubscribe = context.store.subscribe(state => {
    if (state.activePage !== "metrics") return;
    root.dataset.project = state.projectId || "";
    root.dataset.mode = state.connectionMode;
  });
  return () => {
    unsubscribe();
    delete root.dataset.apiDomain;
  };
});
