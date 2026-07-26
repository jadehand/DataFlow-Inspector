import { createPageController } from "./page-controller.js";

export const createDetailPage = () => createPageController("detail", context => {
  const root = document.getElementById("page-detail");
  root.dataset.apiDomain = "detail";
  const unsubscribe = context.store.subscribe(state => {
    if (state.activePage !== "detail") return;
    root.dataset.project = state.projectId || "";
    root.dataset.table = state.table || "";
  });
  return () => {
    unsubscribe();
    delete root.dataset.apiDomain;
  };
});
