import { createPageController } from "./page-controller.js";

export const createAssistantPage = () => createPageController("assistant", context => {
  const root = document.getElementById("page-assistant");
  root.dataset.apiDomain = "assistant";
  const unsubscribe = context.store.subscribe(state => {
    if (state.activePage !== "assistant") return;
    root.dataset.project = state.projectId || "";
    root.dataset.mode = state.connectionMode;
  });
  return () => {
    unsubscribe();
    delete root.dataset.apiDomain;
  };
});
