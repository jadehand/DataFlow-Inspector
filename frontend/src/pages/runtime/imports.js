export function installImports(ctx) {
  const { state, $, ui, apis, store, router, runtime, config, apiRoot, apiOrigin, tableStrategyLabels } = ctx;
  const allAssets = (...args) => ctx.allAssets(...args);
  const ask = (...args) => ctx.ask(...args);
  const bindDetailEditors = (...args) => ctx.bindDetailEditors(...args);
  const clearProjectDerivedState = (...args) => ctx.clearProjectDerivedState(...args);
  const closeMetadataPreview = (...args) => ctx.closeMetadataPreview(...args);
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
  const exportAssetDictionary = (...args) => ctx.exportAssetDictionary(...args);
  const exportCompareResult = (...args) => ctx.exportCompareResult(...args);
  const exportDetailJson = (...args) => ctx.exportDetailJson(...args);
  const exportSelectedAssets = (...args) => ctx.exportSelectedAssets(...args);
  const exportServerDictionary = (...args) => ctx.exportServerDictionary(...args);
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
  const normalizeTable = (...args) => ctx.normalizeTable(...args);
  const openDetailForTable = (...args) => ctx.openDetailForTable(...args);
  const openMetadataPreview = (...args) => ctx.openMetadataPreview(...args);
  const openWizard = (...args) => ctx.openWizard(...args);
  const prepareImpactContext = (...args) => ctx.prepareImpactContext(...args);
  const prepareImpactSeed = (...args) => ctx.prepareImpactSeed(...args);
  const previewDictionaryBulk = (...args) => ctx.previewDictionaryBulk(...args);
  const projectMode = (...args) => ctx.projectMode(...args);
  const renderAssetFlowOptions = (...args) => ctx.renderAssetFlowOptions(...args);
  const renderCompareMeta = (...args) => ctx.renderCompareMeta(...args);
  const renderCompareResult = (...args) => ctx.renderCompareResult(...args);
  const renderDemoContent = (...args) => ctx.renderDemoContent(...args);
  const renderDetailDiff = (...args) => ctx.renderDetailDiff(...args);
  const renderImpactEvidence = (...args) => ctx.renderImpactEvidence(...args);
  const renderImpactResult = (...args) => ctx.renderImpactResult(...args);
  const renderLiveWorkflows = (...args) => ctx.renderLiveWorkflows(...args);
  const renderMetadataPreview = (...args) => ctx.renderMetadataPreview(...args);
  const renderPackageTree = (...args) => ctx.renderPackageTree(...args);
  const renderProjectLoadFailures = (...args) => ctx.renderProjectLoadFailures(...args);
  const renderTableDetail = (...args) => ctx.renderTableDetail(...args);
  const resetLiveOnlyContent = (...args) => ctx.resetLiveOnlyContent(...args);
  const resetWizard = (...args) => ctx.resetWizard(...args);
  const resolveApiHref = (...args) => ctx.resolveApiHref(...args);
  const runBulkDraftEdit = (...args) => ctx.runBulkDraftEdit(...args);
  const runBulkImpactSeed = (...args) => ctx.runBulkImpactSeed(...args);
  const runComparison = (...args) => ctx.runComparison(...args);
  const runImpact = (...args) => ctx.runImpact(...args);
  const saveDetailMetadata = (...args) => ctx.saveDetailMetadata(...args);
  const saveDictionaryBulk = (...args) => ctx.saveDictionaryBulk(...args);
  const selectedAssets = (...args) => ctx.selectedAssets(...args);
  const selectedProjectName = (...args) => ctx.selectedProjectName(...args);
  const setMode = (...args) => ctx.setMode(...args);
  const setProjectOptions = (...args) => ctx.setProjectOptions(...args);
  const setSelectedTable = (...args) => ctx.setSelectedTable(...args);
  const setWizardStep = (...args) => ctx.setWizardStep(...args);
  const switchProject = (...args) => ctx.switchProject(...args);
  const syncDetailDraftHint = (...args) => ctx.syncDetailDraftHint(...args);
  const syncWizardProjects = (...args) => ctx.syncWizardProjects(...args);
  const tagColor = (...args) => ctx.tagColor(...args);
  const unique = (...args) => ctx.unique(...args);
  const unwrap = (...args) => ctx.unwrap(...args);
  const updateCompareMeta = (...args) => ctx.updateCompareMeta(...args);
  const updateLiveSummaries = (...args) => ctx.updateLiveSummaries(...args);
  const updateProjectMode = (...args) => ctx.updateProjectMode(...args);
  const updateVersions = (...args) => ctx.updateVersions(...args);
  const waitForImport = (...args) => ctx.waitForImport(...args);
  function showImportError(error) {
    const box = $("importProgress");
    box.classList.add("show");
    box.style.background = "#fff0f2";
    box.style.color = "var(--danger)";
    box.textContent = "操作失败：" + error.message;
  }
  function tableDrawerStatus(message, isError) {
    const box = $("tableImportStatus");
    box.classList.add("show");
    box.style.background = isError ? "#fff0f2" : "";
    box.style.color = isError ? "var(--danger)" : "";
    box.textContent = message;
  }
  function renderTableStrategyOptions(available, recommended) {
    const ordered = (available && available.length ? available : ["check"]).filter(key => tableStrategyLabels[key]);
    $("tableConflictStrategy").innerHTML = ordered.map(key => `<option value="${escapeHtml(key)}">${escapeHtml(tableStrategyLabels[key])}</option>`).join("");
    $("tableConflictStrategy").value = ordered.includes(recommended) ? recommended : ordered[0];
  }
  function resetTableDrawer() {
    state.tablePreview = null;
    state.selectedRelationIndex = null;
    $("tableDdlInput").value = "";
    $("tableEtlInput").value = "";
    renderTableStrategyOptions(["check"], "check");
    $("tableImportStatus").classList.remove("show");
    $("tableImportStatus").textContent = "";
    $("tablePreviewArea").innerHTML = '<div class="load-state"><strong>尚未预览</strong>先粘贴 DDL，点击“预览解析”。</div>';
  }
  function openTableDrawer() {
    if (state.mode !== "live") return ui.showToast("请先连接真实后端，再执行单表导入");
    if (!state.projectId && !state.projects.length) return ui.showToast("请先创建或导入一个项目");
    resetTableDrawer();
    $("tableDrawer").classList.add("open");
  }
  function closeTableDrawer() {
    $("tableDrawer").classList.remove("open");
    $("tableImportBtn").focus();
  }
  function renderTablePreview(result) {
    state.tablePreview = result;
    const table = result.table || {};
    const conflict = result.conflict;
    const relations = unwrap(result, ["inferred_relations", "relations"]);
    const availableStrategies = unwrap(result, ["available_strategies"]);
    const recommendedStrategy = result.recommended_strategy || (availableStrategies[0] || "check");
    renderTableStrategyOptions(availableStrategies.length ? availableStrategies : ["check"], recommendedStrategy);
    const columns = unwrap(table, ["columns"]).slice(0, 8).map(col => `${col.name} ${col.type}`).join("\n") || "—";
    const badges = [
      table.name ? `表：${table.name}` : "",
      table.layer ? `层级：${table.layer}` : "",
      conflict ? "存在同名冲突" : "未发现同名冲突",
      relations.length ? `推断关系 ${relations.length} 条` : "暂无推断关系"
    ].filter(Boolean);
    const actionButtons = availableStrategies.map(strategy => `<button class="btn ${strategy === recommendedStrategy ? "primary" : ""}" data-table-strategy="${escapeHtml(strategy)}">${escapeHtml(tableStrategyLabels[strategy] || strategy)}</button>`).join("");
    const relationRows = relations.slice(0, 5).map((item, index) => `<div class="diagnostic warning"><span>${escapeHtml(item.source_table || "未知上游")} → ${escapeHtml(item.target_table || table.name || "目标表")}，命中 ${escapeHtml(item.matched_columns_count || 0)} 个字段，置信度 ${escapeHtml(item.confidence || "—")}</span>${availableStrategies.includes("merge_inferred") ? `<button class="btn" style="margin-left:auto" data-table-strategy="merge_inferred" data-relation-index="${escapeHtml(item.index ?? index)}">使用这条关系导入</button>` : ""}</div>`).join("");
    const missingUpstream = unwrap(result, ["missing_upstream_tables"]);
    $("tablePreviewArea").innerHTML = `<h3>解析预览</h3><div class="badge-list">${badges.map(item => `<span>${escapeHtml(item)}</span>`).join("")}</div>${result.message ? `<div class="diagnostic warning">! <span>${escapeHtml(result.message)}</span></div>` : ""}<pre>${escapeHtml(columns)}</pre>${conflict ? `<div class="diagnostic warning">! <span>共同列 ${escapeHtml((conflict.shared_columns || []).length)}，新增 ${escapeHtml((conflict.added_columns || []).length)}，删除 ${escapeHtml((conflict.removed_columns || []).length)}，类型变化 ${escapeHtml((conflict.changed_types || []).length)}</span></div>` : ""}${missingUpstream.length ? `<div class="diagnostic warning">! <span>缺失上游表：${escapeHtml(missingUpstream.join("、"))}</span></div>` : ""}${relationRows}${actionButtons ? `<div class="download-row">${actionButtons}</div>` : ""}`;
  }
  async function runTablePreview() {
    if (!state.projectId) throw new Error("请先选择项目");
    const ddl = $("tableDdlInput").value.trim();
    if (!ddl) throw new Error("请先填写 DDL");
    tableDrawerStatus("正在预览单表解析…", false);
    const result = await apis.assets.previewImport(
      state.projectId,
      JSON.stringify({
        ddl,
        etl_sql: $("tableEtlInput").value.trim()
      })
    );
    renderTablePreview(result);
    tableDrawerStatus(
      result.action === "ready_to_import_precise"
        ? "预览完成：已生成精确血缘，可确认导入。"
        : "预览完成，可继续导入。",
      false
    );
    return result;
  }
  async function runTableImport() {
    if (!state.projectId) throw new Error("请先选择项目");
    const ddl = $("tableDdlInput").value.trim();
    if (!ddl) throw new Error("请先填写 DDL");
    let strategy = $("tableConflictStrategy").value || "check";
    if (strategy === "check" && state.tablePreview?.recommended_strategy) strategy = state.tablePreview.recommended_strategy;
    const confirmedRelationIndex = strategy === "merge_inferred"
      ? (state.selectedRelationIndex ?? (state.tablePreview?.inferred_relations?.[0]?.index ?? 0))
      : null;
    tableDrawerStatus("正在导入单表并刷新项目数据…", false);
    const result = await apis.assets.importOne(
      state.projectId,
      JSON.stringify({
        ddl,
        etl_sql: $("tableEtlInput").value.trim(),
        conflict_strategy: strategy,
        confirmed_relation_index: confirmedRelationIndex
      })
    );
    renderTablePreview(result);
    if (result.requires_decision) {
      tableDrawerStatus(result.message || "后端需要进一步确认，请根据预览结果选择策略。", false);
      return;
    }
    tableDrawerStatus(result.message || "单表导入成功。", false);
    await loadProjectData();
    const page = result.lineage_source === "parsed_from_sql" ? "lineage" : ((result.navigation && result.navigation.page) || "assets");
    closeTableDrawer();
    ui.navigate(page);
    ui.showToast("单表导入完成");
  }
  function normalizePreflight(result) {
    const source = result && (result.summary || result.contents || result.counts || result);
    const count = (...keys) => {
      for (const key of keys) {
        const value = source && source[key];
        if (Array.isArray(value)) return value.length;
        if (Number.isFinite(Number(value))) return Number(value);
      }
      return 0;
    };
    return {
      ddl: count("ddl", "ddl_count", "ddl_files"),
      sql: count("sql", "sql_count", "sql_files"),
      manifest: count("manifest", "manifest_count", "manifest_files"),
      jobs: count("jobs", "jobs_count", "job_files"),
      samples: count("samples", "sample_count", "sample_files"),
      errors: unwrap(result, ["errors", "fatal", "invalid"]),
      warnings: unwrap(result, ["warnings", "diagnostics", "notices"]),
      raw: result
    };
  }
  function renderPreflight(value) {
    const cards = [
      ["DDL", value.ddl, value.ddl > 0],
      ["加工 SQL", value.sql, value.sql > 0],
      ["manifest", value.manifest, true],
      ["jobs", value.jobs, true],
      ["样例", value.samples, true]
    ];
    $("preflightArea").innerHTML = `<div class="preflight-grid">${cards.map(item =>
      `<div class="check-card ${item[2] ? "ok" : "warn"}"><strong>${item[1]}</strong><span>${item[0]}</span></div>`
    ).join("")}</div>${value.errors.map(item => `<div class="diagnostic error">× <span>${escapeHtml(item.message || item.detail || item)}</span></div>`).join("")}${value.warnings.map(item => `<div class="diagnostic warning">! <span>${escapeHtml(item.message || item.detail || item)}</span></div>`).join("")}`;
  }
  async function runPreflight() {
    if (state.mode !== "live") throw new Error("演示模式不会上传或伪造预检结果，请连接真实后端");
    const file = $("importFile").files[0];
    if (!file || !/\.zip$/i.test(file.name)) throw new Error("请选择有效的 ZIP 项目包");
    const pid = await ensureProject();
    $("preflightArea").innerHTML = '<div class="load-state"><strong>正在检查项目包…</strong>核对 DDL、SQL、清单和样例目录。</div>';
    try {
      const result = await apis.imports.preflight(file);
      state.preflight = normalizePreflight(result);
      renderPreflight(state.preflight);
      if (state.preflight.errors.length) throw new Error(`预检发现 ${state.preflight.errors.length} 个阻断错误`);
      if (!state.preflight.sql) throw new Error("项目包至少需要一份加工 SQL；DDL 缺失时仍可导入，但字段分析会不完整");
      return true;
    } catch (error) {
      state.preflight = null;
      $("preflightArea").innerHTML = `<div class="diagnostic error">× <span>真实预检未通过：${escapeHtml(error.message)}。请修正项目包，或确认后端已提供 POST /api/imports/preflight。</span></div>`;
      throw error;
    }
  }
  function analysisSummary(result) {
    const source = result && (result.summary || result.analysis || result.result || result);
    const number = (...keys) => {
      for (const key of keys) {
        const value = source && source[key];
        if (Array.isArray(value)) return value.length;
        if (Number.isFinite(Number(value))) return Number(value);
      }
      return 0;
    };
    const lineage = number("lineage", "lineage_count", "edges") || (number("table_edges") + number("column_edges"));
    return [
      ["数据表", number("tables", "table_count")], ["字段", number("columns", "column_count")],
      ["血缘", lineage], ["指标", number("metrics", "metric_count")],
      ["风险", number("risks", "risk_count", "findings")], ["作业", number("jobs", "job_count")]
    ];
  }
  async function uploadZip() {
    if (state.mode !== "live") throw new Error("演示模式不会上传文件，请先连接后端");
    if (!state.projectId) throw new Error("请先创建或选择项目");
    if (!state.preflight) throw new Error("请先完成真实预检");
    const file = $("importFile").files[0];
    if (!file) throw new Error("请选择 ZIP 项目包");
    const progress = $("importProgress");
    progress.classList.add("show"); progress.style.background = ""; progress.style.color = ""; progress.textContent = "正在上传并启动解析…";
    try {
      const accepted = await apis.imports.upload(
        state.projectId,
        file,
        $("importVersionNote").value.trim()
      );
      const importId = accepted.import_id || accepted.importId || accepted.id || accepted.import?.id;
      const result = await waitForImport(importId, (progressResult) => {
        progress.textContent = progressResult?.message || `正在分析项目包… ${progressResult?.status || "处理中"}`;
      });
      state.importResult = result;
      progress.textContent = "分析完成，正在刷新真实项目数据…";
      await loadProjects();
      $("importConfirm").hidden = true;
      $("importComplete").hidden = false;
      $("completeText").textContent = "后端已完成本次分析，以下摘要来自真实返回结果。";
      $("importSummary").innerHTML = analysisSummary(result).map(item => `<div class="card stat"><div class="label">${escapeHtml(item[0])}</div><div class="value">${escapeHtml(item[1])}</div></div>`).join("");
      progress.classList.remove("show");
      return result;
    } catch (error) {
      showImportError(error);
      throw error;
    }
  }
  Object.assign(ctx, { analysisSummary, closeTableDrawer, normalizePreflight, openTableDrawer, renderPreflight, renderTablePreview, renderTableStrategyOptions, resetTableDrawer, runPreflight, runTableImport, runTablePreview, showImportError, tableDrawerStatus, uploadZip });
}
