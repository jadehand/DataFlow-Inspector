import { createEventScope } from "./event-scope.js";

export function bindImportEvents(ctx) {
  const { state, $, ui } = ctx;
  const scope = createEventScope();

  scope.assign($("tableImportBtn"), "onclick", ctx.openTableDrawer);
  scope.assign($("assetTableImportBtn"), "onclick", ctx.openTableDrawer);
  scope.assign($("importBtn"), "onclick", ctx.openWizard);
  scope.assign($("importsUploadBtn"), "onclick", ctx.openWizard);
  scope.assign($("refreshImportsBtn"), "onclick", async () => {
    try {
      await ctx.refreshImportHistory();
      ui.showToast("导入历史已刷新");
    } catch (error) {
      ui.showToast("导入历史刷新失败：" + error.message);
    }
  });
  scope.assign($("drawer").querySelector(".drawer-close"), "onclick", ctx.closeWizard);
  scope.assign($("wizardCancel"), "onclick", ctx.closeWizard);
  scope.assign($("wizardBack"), "onclick", () => ctx.setWizardStep(Math.max(1, state.wizardStep - 1)));
  scope.assign($("wizardNext"), "onclick", ctx.nextWizardStep);
  document.querySelectorAll('input[name="projectMode"]').forEach(input => {
    scope.assign(input, "onchange", ctx.updateProjectMode);
  });
  document.querySelectorAll(".package-tab").forEach(button => {
    scope.assign(button, "onclick", () => ctx.renderPackageTree(button.dataset.package));
  });
  scope.assign($("importFile"), "onchange", () => {
    const file = $("importFile").files[0];
    state.preflight = null;
    $("fileMeta").classList.toggle("show", Boolean(file));
    if (file) {
      $("fileName").textContent = file.name;
      $("fileSize").textContent = ctx.formatBytes(file.size);
    }
    $("preflightArea").innerHTML = '<div class="load-state"><strong>尚未执行预检</strong>点击“检查项目包”获取后端真实检查结果。</div>';
  });
  scope.assign($("replaceFile"), "onclick", () => $("importFile").click());
  scope.assign($("downloadBlankTemplate"), "onclick", () => {
    if (state.mode === "live") location.href = ctx.apiRoot + "/templates/blank";
    else ctx.downloadGuideFallback();
  });
  scope.assign($("downloadDemoPackage"), "onclick", () => {
    if (state.mode === "live") {
      location.href = ctx.apiRoot + "/templates/demo";
      return;
    }
    const link = document.createElement("a");
    link.href = "../../examples/token-traffic-demo.zip";
    link.download = "token-traffic-demo.zip";
    link.click();
  });
  scope.assign($("gotoAssets"), "onclick", () => {
    ctx.closeWizard();
    ui.navigate("assets");
  });
  scope.assign($("gotoLineage"), "onclick", () => {
    ctx.closeWizard();
    ui.navigate("lineage");
  });
  scope.assign($("tableDrawerClose"), "onclick", ctx.closeTableDrawer);
  scope.assign($("tablePreviewBtn"), "onclick", async () => {
    try {
      await ctx.runTablePreview();
    } catch (error) {
      ctx.tableDrawerStatus("预览失败：" + error.message, true);
    }
  });
  scope.assign($("tableImportRunBtn"), "onclick", async () => {
    try {
      await ctx.runTableImport();
    } catch (error) {
      ctx.tableDrawerStatus("导入失败：" + error.message, true);
    }
  });
  scope.assign($("tablePreviewArea"), "onclick", event => {
    const target = event.target.closest("[data-table-strategy]");
    if (!target) return;
    const strategy = target.dataset.tableStrategy;
    if (strategy) $("tableConflictStrategy").value = strategy;
    if (target.dataset.relationIndex != null) {
      state.selectedRelationIndex = Number(target.dataset.relationIndex);
    }
  });
  scope.assign($("tableDrawer"), "onclick", event => {
    if (event.target === $("tableDrawer")) ctx.closeTableDrawer();
  });

  scope.listen($("drawer"), "keydown", event => {
    if (event.key === "Escape") ctx.closeWizard();
    if (event.key !== "Tab") return;
    const focusable = [...$("drawer").querySelectorAll(
      'button:not([hidden]):not([disabled]),input:not([hidden]),select:not([hidden])'
    )].filter(element => element.offsetParent !== null);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });
  scope.listen($("tableDrawer"), "keydown", event => {
    if (event.key === "Escape") ctx.closeTableDrawer();
  });

  ctx.renderPackageTree(ctx.params.get("package") === "recommended" ? "recommended" : "minimum");
  const wizardDeepLink = Number(ctx.params.get("wizard"));
  if (wizardDeepLink >= 1 && wizardDeepLink <= 4) {
    ctx.defer(() => {
      ctx.openWizard();
      ctx.setWizardStep(wizardDeepLink);
    }, 250);
  }
  return () => scope.cleanup();
}
