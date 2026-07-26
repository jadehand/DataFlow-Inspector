import { createPageController } from "./page-controller.js";

export const createImpactPage = () => createPageController("impact", context => {
  const root = document.getElementById("page-impact");
  root.dataset.apiDomain = "impact";
  const unsubscribe = context.store.subscribe(state => {
    if (state.activePage !== "impact") return;
    root.dataset.project = state.projectId || "";
    root.dataset.hasSeed = String(Boolean(state.impactSeed));
  });
  return () => {
    unsubscribe();
    delete root.dataset.apiDomain;
  };
});
