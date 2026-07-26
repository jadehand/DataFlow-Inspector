import { createPageController } from "./page-controller.js";

export const createComparePage = () => createPageController("compare", context => {
  const root = document.getElementById("page-compare");
  root.dataset.apiDomain = "compare";
  const unsubscribe = context.store.subscribe(state => {
    if (state.activePage !== "compare") return;
    root.dataset.left = state.leftVersion || "";
    root.dataset.right = state.rightVersion || "";
  });
  return () => {
    unsubscribe();
    delete root.dataset.apiDomain;
  };
});
