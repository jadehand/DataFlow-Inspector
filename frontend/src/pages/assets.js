import { createPageController } from "./page-controller.js";

export const createAssetsPage = () => createPageController("assets", context => {
  const root = document.getElementById("page-assets");
  root.dataset.apiDomain = "assets";
  const unsubscribe = context.store.subscribe(state => {
    if (state.activePage !== "assets") return;
    root.dataset.project = state.projectId || "";
    root.dataset.selectionCount = String(state.selectedAssets?.length || 0);
  });
  return () => {
    unsubscribe();
    delete root.dataset.apiDomain;
  };
});
