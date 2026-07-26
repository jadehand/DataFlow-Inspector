export function installImpact(ctx) {
  const { state, $, ui, apis, store, router, runtime, config, apiRoot, apiOrigin, tableStrategyLabels } = ctx;
  const allAssets = (...args) => ctx.allAssets(...args);
  const analysisSummary = (...args) => ctx.analysisSummary(...args);
  const ask = (...args) => ctx.ask(...args);
  const bindDetailEditors = (...args) => ctx.bindDetailEditors(...args);
  const clearProjectDerivedState = (...args) => ctx.clearProjectDerivedState(...args);
  const closeMetadataPreview = (...args) => ctx.closeMetadataPreview(...args);
  const closeTableDrawer = (...args) => ctx.closeTableDrawer(...args);
  const closeWizard = (...args) => ctx.closeWizard(...args);
  const collectDetailDraftPayload = (...args) => ctx.collectDetailDraftPayload(...args);
  const csvLine = (...args) => ctx.csvLine(...args);
  const delay = (...args) => ctx.delay(...args);
  const downloadGuideFallback = (...args) => ctx.downloadGuideFallback(...args);
  const downloadText = (...args) => ctx.downloadText(...args);
  const emptyState = (...args) => ctx.emptyState(...args);
  const enrichTables = (...args) => ctx.enrichTables(...args);
  const ensureProject = (...args) => ctx.ensureProject(...args);
  const escapeHtml = (...args) => ctx.escapeHtml(...args);
  const exportCompareResult = (...args) => ctx.exportCompareResult(...args);
  const exportDetailJson = (...args) => ctx.exportDetailJson(...args);
  const fetchImportMetaByVersion = (...args) => ctx.fetchImportMetaByVersion(...args);
  const fetchMetadataCompare = (...args) => ctx.fetchMetadataCompare(...args);
  const fetchMetadataRevisions = (...args) => ctx.fetchMetadataRevisions(...args);
  const formatBytes = (...args) => ctx.formatBytes(...args);
  const inferFlowFromPath = (...args) => ctx.inferFlowFromPath(...args);
  const layoutNodes = (...args) => ctx.layoutNodes(...args);
  const loadDetailDiff = (...args) => ctx.loadDetailDiff(...args);
  const loadProjectData = (...args) => ctx.loadProjectData(...args);
  const loadProjects = (...args) => ctx.loadProjects(...args);
  const loadTableDetail = (...args) => ctx.loadTableDetail(...args);
  const metadataRevisionPayload = (...args) => ctx.metadataRevisionPayload(...args);
  const nextWizardStep = (...args) => ctx.nextWizardStep(...args);
  const normalizeMetric = (...args) => ctx.normalizeMetric(...args);
  const normalizeNode = (...args) => ctx.normalizeNode(...args);
  const normalizePreflight = (...args) => ctx.normalizePreflight(...args);
  const normalizeTable = (...args) => ctx.normalizeTable(...args);
  const openMetadataPreview = (...args) => ctx.openMetadataPreview(...args);
  const openTableDrawer = (...args) => ctx.openTableDrawer(...args);
  const openWizard = (...args) => ctx.openWizard(...args);
  const previewDictionaryBulk = (...args) => ctx.previewDictionaryBulk(...args);
  const projectMode = (...args) => ctx.projectMode(...args);
  const renderAssetFlowOptions = (...args) => ctx.renderAssetFlowOptions(...args);
  const renderCompareMeta = (...args) => ctx.renderCompareMeta(...args);
  const renderCompareResult = (...args) => ctx.renderCompareResult(...args);
  const renderDemoContent = (...args) => ctx.renderDemoContent(...args);
  const renderDetailDiff = (...args) => ctx.renderDetailDiff(...args);
  const renderLiveWorkflows = (...args) => ctx.renderLiveWorkflows(...args);
  const renderMetadataPreview = (...args) => ctx.renderMetadataPreview(...args);
  const renderPackageTree = (...args) => ctx.renderPackageTree(...args);
  const renderPreflight = (...args) => ctx.renderPreflight(...args);
  const renderProjectLoadFailures = (...args) => ctx.renderProjectLoadFailures(...args);
  const renderTableDetail = (...args) => ctx.renderTableDetail(...args);
  const renderTablePreview = (...args) => ctx.renderTablePreview(...args);
  const renderTableStrategyOptions = (...args) => ctx.renderTableStrategyOptions(...args);
  const resetLiveOnlyContent = (...args) => ctx.resetLiveOnlyContent(...args);
  const resetTableDrawer = (...args) => ctx.resetTableDrawer(...args);
  const resetWizard = (...args) => ctx.resetWizard(...args);
  const resolveApiHref = (...args) => ctx.resolveApiHref(...args);
  const runPreflight = (...args) => ctx.runPreflight(...args);
  const runTableImport = (...args) => ctx.runTableImport(...args);
  const runTablePreview = (...args) => ctx.runTablePreview(...args);
  const saveDetailMetadata = (...args) => ctx.saveDetailMetadata(...args);
  const saveDictionaryBulk = (...args) => ctx.saveDictionaryBulk(...args);
  const selectedAssets = (...args) => ctx.selectedAssets(...args);
  const selectedProjectName = (...args) => ctx.selectedProjectName(...args);
  const setMode = (...args) => ctx.setMode(...args);
  const setProjectOptions = (...args) => ctx.setProjectOptions(...args);
  const setSelectedTable = (...args) => ctx.setSelectedTable(...args);
  const setWizardStep = (...args) => ctx.setWizardStep(...args);
  const showImportError = (...args) => ctx.showImportError(...args);
  const switchProject = (...args) => ctx.switchProject(...args);
  const syncDetailDraftHint = (...args) => ctx.syncDetailDraftHint(...args);
  const syncWizardProjects = (...args) => ctx.syncWizardProjects(...args);
  const tableDrawerStatus = (...args) => ctx.tableDrawerStatus(...args);
  const tagColor = (...args) => ctx.tagColor(...args);
  const unique = (...args) => ctx.unique(...args);
  const unwrap = (...args) => ctx.unwrap(...args);
  const updateCompareMeta = (...args) => ctx.updateCompareMeta(...args);
  const updateLiveSummaries = (...args) => ctx.updateLiveSummaries(...args);
  const updateProjectMode = (...args) => ctx.updateProjectMode(...args);
  const updateVersions = (...args) => ctx.updateVersions(...args);
  const uploadZip = (...args) => ctx.uploadZip(...args);
  const waitForImport = (...args) => ctx.waitForImport(...args);
  async function runImpact() {
    if (state.mode !== "live") {
      $("impactResult").classList.remove("show");
      return ui.showToast("演示模式不生成伪影响结果，请连接真实项目后分析");
    }
    const button = $("runImpact"); button.disabled = true; button.textContent = "正在沿真实血缘分析…";
    $("impactResult").classList.remove("show");
    try {
      const result = await apis.impact.analyze(
        state.projectId,
        Object.assign({
          object:$("changeObject").value,
          change_type:$("changeType").value,
          before:$("beforeValue").value,
          after:$("afterValue").value
        }, state.impactSeed || {}));
      $("impactResult").classList.add("show");
      renderImpactResult(result);
      ui.showToast("真实影响分析完成：" + (result.affected_count ?? result.total_affected ?? "结果已返回"));
    } catch (error) {
      $("impactScore").textContent = "—";
      $("impactRiskLabel").textContent = "分析失败";
      $("impactHeadline").textContent = "无法生成真实影响结果";
      $("impactSummaryText").textContent = error.message;
      $("impactTree").innerHTML = emptyState("影响路径不可用", "后端未返回有效结果。");
      $("impactRecommendations").innerHTML = emptyState("暂无建议", "请修正错误后重新分析。");
      $("impactResult").classList.add("show");
      ui.showToast("影响分析失败：" + error.message);
    }
    finally { button.disabled = false; button.textContent = "重新分析"; }
  }
  function prepareImpactContext({object, changeType, before, after, context}) {
    $("changeObject").value = object || "";
    $("changeType").value = changeType || "加工逻辑变化";
    $("beforeValue").value = before ?? "";
    $("afterValue").value = after ?? "";
    $("impactContext").textContent = context || "已从其他页面带入对象与差异。";
  }
  function prepareImpactSeed(seed) {
    state.impactSeed = Object.assign({}, seed || {});
  }
  function renderImpactEvidence(result) {
    const scopeLabel = $("impactEvidenceScope");
    const list = $("impactEvidenceList");
    if (!scopeLabel || !list) return;
    const evidence = result.diff_evidence || [];
    scopeLabel.textContent = result.evidence_scope === "metadata_revision"
      ? "来自元数据修订比较"
      : result.evidence_scope === "project"
        ? "来自版本比较"
        : "未带入版本证据";
    list.innerHTML = evidence.length
      ? evidence.slice(0, 8).map(item => `<div class="diff-card"><strong class="mono">${escapeHtml(item.object || item.table || "对象")}</strong><ul><li>范围：${escapeHtml(item.scope || "—")}</li><li>类型：${escapeHtml(item.change_type || "changed")}</li><li>字段：${escapeHtml(Object.keys(item.details || item.changes || {}).join("、") || "—")}</li></ul></div>`).join("")
      : '<div class="empty-shell"><strong>暂无命中证据</strong>当前影响分析基于血缘传播返回，没有额外匹配到该对象的版本差异项。</div>';
  }
  function renderImpactResult(result) {
    const riskMap = {high:["高风险",84], medium:["中风险",63], low:["低风险",32]};
    const riskPayload = result.risk && typeof result.risk === "object" ? result.risk : {};
    const risk = String(result.risk_level || riskPayload.level || result.risk || "low").toLowerCase();
    const [label, defaultScore] = riskMap[risk] || ["待评估", 0];
    const scoreValue = result.risk_score ?? result.score ?? riskPayload.score;
    const score = Number.isFinite(Number(scoreValue))
      ? Number(scoreValue)
      : defaultScore;
    $("impactScore").textContent = String(score);
    const scoreCircle = $("impactScore").closest(".score-circle");
    if (scoreCircle) {
      const normalizedScore = Math.max(0, Math.min(100, score));
      scoreCircle.style.background = `conic-gradient(var(--warning) 0 ${normalizedScore}%,#f2e2ca ${normalizedScore}%)`;
    }
    $("impactRiskLabel").textContent = label;
    const impacts = result.transitive_impacts || result.impacts || result.affected_objects || [];
    const total = result.affected_count ?? result.total_affected ?? impacts.length;
    $("impactHeadline").textContent = `变更将传递到 ${total} 个下游对象`;
    const scripts = result.scripts || result.affected_scripts || [];
    const metrics = result.metrics || result.affected_metrics || [];
    const adsTables = result.ads_tables || result.affected_ads || [];
    $("impactSummaryText").textContent = `${scripts.length} 个脚本、${metrics.length} 个指标、${adsTables.length} 张 ADS 需要关注。`;
    const objectName = $("changeObject").value || result.change?.object || "变更对象";
    const paths = result.paths?.length ? result.paths : impacts.map(item => (
      typeof item === "string" ? { target: item } : item
    ));
    $("impactTree").innerHTML = paths.length
      ? [`<div class="tree-row" style="--depth:0"><span class="tag" style="--tag:var(--accent)">ROOT</span><strong class="mono">${escapeHtml(objectName)}</strong></div>`].concat(paths.slice(0, 12).map((item, index) => {
        const target = item.target || item.object || item.name || item.table || "—";
        const depth = item.depth ?? Math.min(index + 1, 4);
        return `<div class="tree-row" style="--depth:${Math.min(depth, 4)}"><span class="tree-line"></span><span class="tag" style="--tag:${String(target).toLowerCase().includes("ads") ? "var(--ads)" : "var(--dws)"}">${escapeHtml(String(target).split(".")[0] || "TABLE")}</span><span class="mono">${escapeHtml(target)}</span></div>`;
      })).join("")
      : emptyState("暂无传播路径", "后端未找到该对象的传递下游。");
    const recommendations = result.recommendations || result.suggestions || [];
    $("impactRecommendations").innerHTML = recommendations.length
      ? recommendations.map((item, index) => {
        const text = typeof item === "string" ? item : item.message || item.title || item.action || JSON.stringify(item);
        return `<div class="flow-row"><div class="flow-code">${index + 1}</div><div><strong>${escapeHtml(text)}</strong><div class="table-desc">${index === 0 ? "建议先修改上游定义，再顺序回归下游。" : "来自真实影响分析返回。"}</div></div></div>`;
      }).join("")
      : emptyState("暂无建议", "后端未返回建议，请结合传播路径人工确认。");
    renderImpactEvidence(result);
  }
  async function runComparison() {
    if (state.mode !== "live") return ui.showToast("当前为演示版本比较，未调用后端");
    try {
      const result = await apis.compare.project(
        state.projectId,
        $("compareLeft").value,
        $("compareRight").value
      );
      await fetchMetadataRevisions();
      await fetchMetadataCompare();
      renderCompareResult(result);
      await updateCompareMeta();
      ui.showToast("真实版本语义比较完成");
    } catch (error) { ui.showToast("版本比较失败：" + error.message); }
  }
  async function openDetailForTable(name) {
    if (!name) return;
    if (state.mode !== "live") {
      ui.navigate("detail", { table: name });
      return ui.showToast("演示模式下仅展示静态详情样式");
    }
    try {
      await loadTableDetail(name);
      ui.navigate("detail", { table: name });
    } catch (error) {
      ui.showToast("表详情加载失败：" + error.message);
    }
  }
  async function exportServerDictionary() {
    if (state.mode !== "live" || !state.projectId) return ui.showToast("请先连接真实后端并选择项目");
    try {
      const blob = await apis.dictionary.exportFile(state.projectId);
      downloadText(`data-dictionary-project-${state.projectId}.csv`, await blob.text(), "text/csv;charset=utf-8");
    } catch (error) {
      ui.showToast("字段字典导出失败：" + error.message);
    }
  }
  function exportAssetDictionary(rows, filename) {
    const targetRows = rows && rows.length ? rows : allAssets();
    if (!targetRows.length) return ui.showToast("当前没有可导出的资产");
    const header = ["table_name","layer","flow","partition","grain","upstream","etl","ddl","owner","frequency","fields","status","note"];
    const csv = [csvLine(header)].concat(targetRows.map(item => csvLine([
      item.name, item.layer, item.flow, item.partition, item.grain, item.upstream, item.etl, item.ddl,
      item.owner, item.frequency, item.fields, item.risk ? "risk" : "ok", item.note
    ]))).join("\n");
    downloadText(filename || "dataflow-assets.csv", csv, "text/csv;charset=utf-8");
  }
  function exportSelectedAssets() {
    const rows = selectedAssets();
    if (!rows.length) return ui.showToast("请先勾选资产");
    exportAssetDictionary(rows, "dataflow-selected-assets.csv");
  }
  async function runBulkDraftEdit() {
    const rows = selectedAssets();
    if (!rows.length) return ui.showToast("请先勾选需要批量编辑的资产");
    const owner = prompt("批量填写负责人（留空表示不修改）", rows[0].owner || "");
    if (owner === null) return;
    const frequency = prompt("批量填写更新频率（留空表示不修改）", rows[0].frequency || "");
    if (frequency === null) return;
    const retention = prompt("批量填写留存策略（留空表示不修改）", rows[0].retention || "");
    if (retention === null) return;
    const note = prompt("批量补充备注（留空表示不修改）", rows[0].note || "");
    if (note === null) return;
    const patch = {};
    if (owner.trim()) patch.owner = owner.trim();
    if (frequency.trim()) patch.frequency = frequency.trim();
    if (retention.trim()) patch.retention = retention.trim();
    if (note.trim()) patch.note = note.trim();
    if (!Object.keys(patch).length) return ui.showToast("没有新的草稿字段需要应用");
    ui.applyAssetDrafts(patch);
    try {
      state.metadataPreviewContext = {
        defaultSource: "asset_bulk_edit",
        reason: `批量更新 ${rows.length} 个资产的表级元数据`
      };
      const payload = {
        tables: rows.map(item => ({
          table_name: item.name,
          display_name: item.displayName || "",
          owner: patch.owner || item.owner || "",
          update_frequency: patch.frequency || item.frequency || "",
          retention: patch.retention || item.retention || "",
          note: patch.note || item.note || ""
        })),
        columns: [],
        revision_meta: metadataRevisionPayload()
      };
      const preview = await previewDictionaryBulk(payload);
      const ok = await openMetadataPreview(preview, `批量保存前预览 · ${rows.length} 个资产`);
      if (!ok) return ui.showToast("已取消批量保存");
      payload.revision_meta = metadataRevisionPayload();
      await saveDictionaryBulk(payload);
      await loadProjectData();
      ui.showToast(`已批量保存 ${rows.length} 个资产的元数据`);
    } catch (error) {
      ui.showToast(`批量保存失败：${error.message}`);
    }
  }
  function runBulkImpactSeed() {
    const rows = selectedAssets();
    if (!rows.length) return ui.showToast("请先勾选资产");
    const first = rows[0];
    prepareImpactContext({
      object: first.name,
      changeType: "加工逻辑变化",
      before: first.etl || first.ddl || "当前版本",
      after: `${rows.length} 个选中资产需批量回归`,
      context: `已从资产页带入 ${rows.length} 个选中资产；当前以 ${first.name} 作为根对象。`
    });
    state.impactSeed = null;
    ui.navigate("impact");
  }
  Object.assign(ctx, { exportAssetDictionary, exportSelectedAssets, exportServerDictionary, openDetailForTable, prepareImpactContext, prepareImpactSeed, renderImpactEvidence, renderImpactResult, runBulkDraftEdit, runBulkImpactSeed, runComparison, runImpact });
}
