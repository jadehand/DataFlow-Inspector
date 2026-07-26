import { createEventScope } from "./event-scope.js";

export function bindCatalogEvents(ctx) {
  const { state, $, ui } = ctx;
  const scope = createEventScope();

  scope.assign($("exportAssetDictionaryBtn"), "onclick", () => ctx.exportServerDictionary());
  scope.assign($("bulkEditBtn"), "onclick", ctx.runBulkDraftEdit);
  scope.assign($("bulkImpactBtn"), "onclick", ctx.runBulkImpactSeed);
  scope.assign($("bulkExportBtn"), "onclick", ctx.exportSelectedAssets);
  scope.assign($("metadataPreviewClose"), "onclick", () => ctx.closeMetadataPreview(false));
  scope.assign($("metadataPreviewCancel"), "onclick", () => ctx.closeMetadataPreview(false));
  scope.assign($("metadataPreviewConfirm"), "onclick", () => ctx.closeMetadataPreview(true));
  scope.assign($("metadataPreviewDrawer"), "onclick", event => {
    if (event.target === $("metadataPreviewDrawer")) ctx.closeMetadataPreview(false);
  });
  scope.assign($("detailSaveBtn"), "onclick", ctx.saveDetailMetadata);
  scope.assign($("detailLineageBtn"), "onclick", () => {
    if (!state.selectedTableName) return ui.showToast("请先打开一张表详情");
    ui.navigate("lineage", { focus: state.selectedTableName });
    const focused = ui.focusNode(state.selectedTableName);
    if (!focused) {
      ctx.defer(() => {
        const done = ui.focusNode(state.selectedTableName);
        ui.focusHint(done
          ? `已聚焦 ${state.selectedTableName}`
          : `未在当前血缘图中定位到 ${state.selectedTableName}`);
      }, 80);
    } else {
      ui.focusHint(`已聚焦 ${state.selectedTableName}`);
    }
  });
  scope.assign($("detailImpactBtn"), "onclick", () => {
    if (!state.selectedTableName) return ui.showToast("请先打开一张表详情");
    ctx.prepareImpactContext({
      object: state.selectedTableName,
      changeType: "加工逻辑变化",
      before: state.selectedTableDetail?.table?.ddl_file || "当前定义",
      after: "待调整",
      context: `已从表详情带入 ${state.selectedTableName}。`
    });
    state.impactSeed = null;
    ui.navigate("impact");
  });
  scope.assign($("detailExportBtn"), "onclick", ctx.exportDetailJson);
  scope.assign($("metricExportBtn"), "onclick", () => ui.exportMetrics());
  scope.assign($("lineageMode"), "onchange", () => {
    ctx.refreshLineage().catch(error => ui.showToast("血缘模式切换失败：" + error.message));
  });
  scope.assign($("lineageDepth"), "onchange", () => {
    ctx.refreshLineage().catch(error => ui.showToast("血缘深度切换失败：" + error.message));
  });
  scope.assign($("lineageFocusBtn"), "onclick", () => {
    const target = state.selectedTableName || ctx.store.getState().focus || $("lineageSearch").value.trim();
    if (!target) return ui.focusHint("请先搜索或从资产详情指定聚焦对象");
    const focused = ui.focusNode(target);
    ui.focusHint(focused ? `已聚焦 ${target}` : `未在当前血缘图中定位到 ${target}`);
  });
  scope.assign($("highlightPath"), "onclick", () => ui.highlightMainPath());

  ui.setCallbacks({
    assetSelect: ctx.openDetailForTable,
    nodeSelect: name => {
      ctx.setSelectedTable(name);
      ctx.router.update({ focus: name, table: name }, { replace: true });
    },
    assetSelectionChange: rows => {
      state.selectedAssets = rows || [];
      $("bulkImpactBtn").disabled = !rows.length;
      $("bulkExportBtn").disabled = !rows.length;
      $("bulkEditBtn").disabled = !rows.length;
    }
  });

  return () => {
    scope.cleanup();
    ui.setCallbacks({
      assetSelect: null,
      nodeSelect: null,
      assetSelectionChange: null
    });
    if (state.metadataPreviewResolver) state.metadataPreviewResolver(false);
    state.metadataPreviewResolver = null;
  };
}
