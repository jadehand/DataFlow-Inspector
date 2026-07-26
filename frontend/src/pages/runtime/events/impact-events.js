import { createEventScope } from "./event-scope.js";

export function bindImpactEvents(ctx) {
  const { state, $, ui, router } = ctx;
  const scope = createEventScope();

  scope.assign($("runImpact"), "onclick", ctx.runImpact);
  scope.assign($("runCompare"), "onclick", ctx.runComparison);
  scope.assign($("exportCompareBtn"), "onclick", ctx.exportCompareResult);
  scope.assign($("compareLeft"), "onchange", () => {
    router.update({ leftVersion: $("compareLeft").value });
    ctx.updateCompareMeta();
  });
  scope.assign($("compareRight"), "onchange", () => {
    router.update({ rightVersion: $("compareRight").value });
    ctx.updateCompareMeta();
  });
  scope.assign($("compareChangeList"), "onclick", event => {
    const detailTarget = event.target.closest("[data-compare-open-detail]");
    if (detailTarget) {
      ctx.openDetailForTable(detailTarget.dataset.compareOpenDetail);
      return;
    }
    const impactTarget = event.target.closest("[data-compare-impact]");
    if (!impactTarget) return;
    const scopeName = impactTarget.dataset.compareScope || "project";
    ctx.prepareImpactContext({
      object: impactTarget.dataset.compareImpact,
      changeType: "加工逻辑变化",
      before: "上一版本",
      after: "当前版本",
      context: `已从版本比较带入 ${impactTarget.dataset.compareImpact}。`
    });
    if (scopeName === "metadata_revision" && state.metadataCompareResult) {
      ctx.prepareImpactSeed({
        compare_scope: "metadata_revision",
        left_revision: Number(state.metadataCompareResult.left_revision?.revision),
        right_revision: Number(state.metadataCompareResult.right_revision?.revision)
      });
    } else {
      ctx.prepareImpactSeed({
        compare_scope: "project",
        left_version: Number($("compareLeft").value),
        right_version: Number($("compareRight").value)
      });
    }
    ui.navigate("impact");
  });
  return () => scope.cleanup();
}
