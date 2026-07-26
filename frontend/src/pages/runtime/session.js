export function installSession(ctx) {
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
  const loadTableDetail = (...args) => ctx.loadTableDetail(...args);
  const metadataRevisionPayload = (...args) => ctx.metadataRevisionPayload(...args);
  const nextWizardStep = (...args) => ctx.nextWizardStep(...args);
  const normalizeMetric = (...args) => ctx.normalizeMetric(...args);
  const normalizeNode = (...args) => ctx.normalizeNode(...args);
  const normalizePreflight = (...args) => ctx.normalizePreflight(...args);
  const normalizeTable = (...args) => ctx.normalizeTable(...args);
  const openDetailForTable = (...args) => ctx.openDetailForTable(...args);
  const openMetadataPreview = (...args) => ctx.openMetadataPreview(...args);
  const openTableDrawer = (...args) => ctx.openTableDrawer(...args);
  const openWizard = (...args) => ctx.openWizard(...args);
  const prepareImpactContext = (...args) => ctx.prepareImpactContext(...args);
  const prepareImpactSeed = (...args) => ctx.prepareImpactSeed(...args);
  const previewDictionaryBulk = (...args) => ctx.previewDictionaryBulk(...args);
  const renderAssetFlowOptions = (...args) => ctx.renderAssetFlowOptions(...args);
  const renderCompareMeta = (...args) => ctx.renderCompareMeta(...args);
  const renderCompareResult = (...args) => ctx.renderCompareResult(...args);
  const renderDetailDiff = (...args) => ctx.renderDetailDiff(...args);
  const renderImpactEvidence = (...args) => ctx.renderImpactEvidence(...args);
  const renderImpactResult = (...args) => ctx.renderImpactResult(...args);
  const renderMetadataPreview = (...args) => ctx.renderMetadataPreview(...args);
  const renderPackageTree = (...args) => ctx.renderPackageTree(...args);
  const renderPreflight = (...args) => ctx.renderPreflight(...args);
  const renderTableDetail = (...args) => ctx.renderTableDetail(...args);
  const renderTablePreview = (...args) => ctx.renderTablePreview(...args);
  const renderTableStrategyOptions = (...args) => ctx.renderTableStrategyOptions(...args);
  const resetLiveOnlyContent = (...args) => ctx.resetLiveOnlyContent(...args);
  const resetTableDrawer = (...args) => ctx.resetTableDrawer(...args);
  const resetWizard = (...args) => ctx.resetWizard(...args);
  const resolveApiHref = (...args) => ctx.resolveApiHref(...args);
  const runBulkDraftEdit = (...args) => ctx.runBulkDraftEdit(...args);
  const runBulkImpactSeed = (...args) => ctx.runBulkImpactSeed(...args);
  const runComparison = (...args) => ctx.runComparison(...args);
  const runImpact = (...args) => ctx.runImpact(...args);
  const runPreflight = (...args) => ctx.runPreflight(...args);
  const runTableImport = (...args) => ctx.runTableImport(...args);
  const runTablePreview = (...args) => ctx.runTablePreview(...args);
  const saveDetailMetadata = (...args) => ctx.saveDetailMetadata(...args);
  const saveDictionaryBulk = (...args) => ctx.saveDictionaryBulk(...args);
  const selectedAssets = (...args) => ctx.selectedAssets(...args);
  const setMode = (...args) => ctx.setMode(...args);
  const setSelectedTable = (...args) => ctx.setSelectedTable(...args);
  const setWizardStep = (...args) => ctx.setWizardStep(...args);
  const showImportError = (...args) => ctx.showImportError(...args);
  const switchProject = (...args) => ctx.switchProject(...args);
  const syncDetailDraftHint = (...args) => ctx.syncDetailDraftHint(...args);
  const tableDrawerStatus = (...args) => ctx.tableDrawerStatus(...args);
  const tagColor = (...args) => ctx.tagColor(...args);
  const unique = (...args) => ctx.unique(...args);
  const unwrap = (...args) => ctx.unwrap(...args);
  const updateProjectMode = (...args) => ctx.updateProjectMode(...args);
  const uploadZip = (...args) => ctx.uploadZip(...args);
  const waitForImport = (...args) => ctx.waitForImport(...args);
  function setProjectOptions() {
    const select = $("projectSelect");
    select.innerHTML = state.projects.map(p => `<option value="${escapeHtml(p.id)}">${escapeHtml(p.name || p.project_name || p.id)}</option>`).join("");
    if (state.projectId != null) select.value = String(state.projectId);
    syncWizardProjects();
  }
  function syncWizardProjects() {
    const select = $("wizardProjectSelect");
    if (!select) return;
    select.innerHTML = state.projects.length
      ? state.projects.map(p => `<option value="${escapeHtml(p.id)}">${escapeHtml(p.name || p.project_name || p.id)}</option>`).join("")
      : '<option value="">尚无项目，请选择“创建新项目”</option>';
    if (state.projectId != null) select.value = String(state.projectId);
  }
  async function loadProjects() {
    setMode("connecting");
    try {
      const payload = await apis.projects.list();
      state.projects = unwrap(payload, ["projects","items","data"]);
      if (!state.projects.length) {
        $("projectSelect").innerHTML = '<option value="">尚无项目，请导入项目包</option>';
        state.projectId = null;
        ui.setTables([]); ui.setMetrics([]); ui.setNodes([]); ui.setEdges([]);
        ui.renderAssets(); ui.renderMetrics(); ui.renderGraph();
        syncWizardProjects();
        setMode("live");
        return;
      }
      const requestedProject = state.projects.find(project =>
        String(project.id) === String(state.projectId)
      );
      state.projectId = requestedProject?.id || state.projects[0].id;
      if (String(store.getState().projectId || "") !== String(state.projectId)) {
        router.update({ projectId: state.projectId }, { replace: true });
      }
      setProjectOptions();
      setMode("live");
      await loadProjectData();
    } catch (error) {
      setMode("error", "无法连接后端：" + error.message + "。请检查服务或显式选择演示模式。");
      $("projectSelect").innerHTML = '<option value="">后端不可用</option>';
    }
  }
  async function loadProjectData() {
    if (!state.projectId || state.mode !== "live") return;
    const generation = store.getState().requestGeneration;
    const id = state.projectId;
    const results = await Promise.allSettled([
      apis.assets.list(id),
      apis.lineage.get(id),
      apis.catalog.workflows(id),
      apis.catalog.metrics(id),
      apis.catalog.findings(id),
      apis.imports.list(id),
      apis.dictionary.revisions(id)
    ]);
    if (generation !== store.getState().requestGeneration || id !== state.projectId) return;
    const failures = results.filter(r => r.status === "rejected");
    const tableList = results[0].status === "fulfilled" ? unwrap(results[0].value, ["tables","items","data"]) : [];
    const lineagePayload = results[1].status === "fulfilled" ? results[1].value : null;
    let rawNodes = unwrap(lineagePayload, ["nodes","tables","items"]);
    const rawEdges = unwrap(lineagePayload, ["edges","lineage","data"]);
    const workflowPayload = results[2].status === "fulfilled" ? results[2].value : null;
    const jobs = unwrap(workflowPayload, ["jobs","items","data"]);
    const findingPayload = results[4].status === "fulfilled" ? results[4].value : null;
    const findings = unwrap(findingPayload, ["findings","risks","items","data"]);
    const enrichedTables = enrichTables(tableList, rawEdges, jobs, findings);
    runtime.liveStore.replace({
      projects: state.projects,
      versions: results[5].status === "fulfilled" ? unwrap(results[5].value, ["imports", "versions", "items", "data"]) : [],
      tables: enrichedTables,
      metrics: results[3].status === "fulfilled" ? unwrap(results[3].value, ["metrics", "items", "data"]) : [],
      lineage: { nodes: rawNodes, edges: rawEdges },
      workflows: jobs,
      findings
    });
    renderAssetFlowOptions(enrichedTables);
    ui.setTables(enrichedTables.map(normalizeTable));
    ui.renderAssets();
    if (!rawNodes.length && rawEdges.length) {
      const tableMap = new Map(tableList.map(t => [t.name, t]));
      const names = [...new Set(rawEdges.flatMap(e => [e.source, e.target]))];
      rawNodes = names.map(name => Object.assign({id:name,name}, tableMap.get(name) || {}));
    }
    ui.setNodes(layoutNodes(rawNodes));
    ui.setEdges(rawEdges);
    ui.renderGraph();
    const metricList = results[3].status === "fulfilled" ? unwrap(results[3].value, ["metrics","items","data"]) : [];
    ui.setMetrics(metricList.map(normalizeMetric));
    ui.renderMetrics();
    const listedVersions = results[5].status === "fulfilled" ? unwrap(results[5].value, ["imports","versions","items","data"]) : [];
    state.versions = await enrichImportHistory(listedVersions);
    if (generation !== store.getState().requestGeneration || id !== state.projectId) return;
    runtime.liveStore.replace({ versions: state.versions });
    state.metadataRevisions = results[6].status === "fulfilled" ? unwrap(results[6].value, ["revisions","items","data"]) : [];
    updateLiveSummaries(tableList, jobs, findings, metricList);
    renderProjectLoadFailures(results);
    updateVersions();
    renderImportHistory(state.versions);
    renderCompareMeta(null, null);
    if (state.selectedTableName) {
      try { await loadTableDetail(state.selectedTableName); } catch (_) {}
    }
    if (state.routeFocus) {
      const focused = ui.focusNode(state.routeFocus);
      ui.focusHint(focused ? `已聚焦 ${state.routeFocus}` : `未在当前血缘图中定位到 ${state.routeFocus}`);
    }
    if (failures.length) ui.showToast(`真实项目已加载，${failures.length} 类数据接口暂不可用`);
    else ui.showToast("真实项目数据已加载");
  }
  function renderProjectLoadFailures(results) {
    const errorMessage = result => result.reason?.message || "接口请求失败";
    if (results[0].status === "rejected") {
      $("assetRows").innerHTML = `<tr><td colspan="8">${emptyState("数据资产加载失败", errorMessage(results[0]))}</td></tr>`;
    }
    if (results[1].status === "rejected") {
      $("graphArea").innerHTML = emptyState("血缘加载失败", errorMessage(results[1]));
    }
    if (results[2].status === "rejected") {
      document.querySelector("#page-workflow .workflow-canvas").innerHTML = emptyState("作业流加载失败", errorMessage(results[2]));
      document.querySelector("#page-overview .flow-list").innerHTML = emptyState("作业流加载失败", errorMessage(results[2]));
    }
    if (results[3].status === "rejected") {
      $("metricGrid").innerHTML = `<div class="card">${emptyState("指标加载失败", errorMessage(results[3]))}</div>`;
    }
    if (results[4].status === "rejected") {
      document.querySelector("#page-overview .risk-list").innerHTML = emptyState("风险结果加载失败", errorMessage(results[4]));
    }
  }
  function updateLiveSummaries(tableList, jobs, findings, metricList) {
    const values = document.querySelectorAll("#page-overview .stat .value");
    if (values[0]) values[0].textContent = String(tableList.length);
    if (values[1]) values[1].textContent = String(tableList.reduce((total, table) =>
      total + (table.column_count ?? (table.columns || table.fields || []).length), 0));
    if (values[2]) values[2].textContent = String(metricList.length);
    if (values[3]) values[3].textContent = String(findings.length);
    document.querySelectorAll("#page-overview .stat .delta").forEach(node => { node.textContent = "来自当前项目真实分析"; });
    $("sideStats").textContent = `${tableList.length} 张表 · ${metricList.length} 个指标 · ${findings.length} 项风险`;
    const project = state.projects.find(item => String(item.id) === String(state.projectId));
    const projectTitle = document.querySelector("#page-overview h1");
    if (projectTitle && project) projectTitle.textContent = project.name || project.project_name || "数据加工项目";
    renderLiveWorkflows(jobs);
    const workflowStats = document.querySelectorAll("#page-workflow .grid.cols-3 .eyebrow");
    if (workflowStats[0]) workflowStats[0].textContent = `${jobs.length} jobs`;
    if (workflowStats[1]) workflowStats[1].textContent = `${jobs.filter(j => j.confirmed === false || j.status === "inferred").length} inferred`;
    const riskList = document.querySelector("#page-overview .risk-list");
    if (riskList) riskList.innerHTML = findings.length
      ? findings.slice(0, 3).map(f => `<div class="risk ${f.severity === "high" ? "high" : ""}"><div class="risk-icon">!</div><div><strong>${escapeHtml(f.message || f.title || f.code || "质量风险")}</strong><p>${escapeHtml(f.file || f.object || "来自真实项目分析")}</p></div></div>`).join("")
      : emptyState("暂无风险结果", "当前真实分析未返回质量发现。");
  }
  function renderLiveWorkflows(jobs) {
    const canvas = document.querySelector("#page-workflow .workflow-canvas");
    const overview = document.querySelector("#page-overview .flow-list");
    if (!canvas || !overview) return;
    if (!jobs.length) {
      canvas.innerHTML = emptyState("暂无作业流", "当前真实项目未返回作业数据。");
      overview.innerHTML = emptyState("暂无作业流", "导入 jobs.csv 或可识别的 SQL 后展示。");
      return;
    }
    const jobHtml = jobs.map((job, index) => `<div class="job"><span class="num">${index + 1} · ${escapeHtml(job.layer || job.type || "JOB")}</span><strong>${escapeHtml(job.name || job.job_name || job.id || "未命名作业")}</strong><small>${escapeHtml(job.script_path || job.file || job.schedule || "来自真实分析")}</small></div>`).join('<span class="job-line"></span>');
    canvas.innerHTML = `<div class="job-chain">${jobHtml}</div>`;
    overview.innerHTML = jobs.slice(0, 3).map((job, index) => `<div class="flow-row"><div class="flow-code">${index + 1}</div><div><strong>${escapeHtml(job.name || job.job_name || job.id || "未命名作业")}</strong><div class="flow-meta"><span>${escapeHtml(job.script_path || job.file || "真实分析")}</span></div></div><span class="health ${job.confirmed === false || job.status === "inferred" ? "warn" : "ok"}">${job.confirmed === false || job.status === "inferred" ? "待确认" : "已识别"}</span></div>`).join("");
  }
  function renderDemoContent() {
    const demo = runtime.demoStore?.getSnapshot?.() || {};
    const stats = demo.project?.stats || {};
    const values = document.querySelectorAll("#page-overview .stat .value");
    [stats.tables, stats.fields, stats.metrics, stats.risks].forEach((value, index) => {
      if (values[index]) values[index].textContent = String(value || 0);
    });
    document.querySelectorAll("#page-overview .stat .delta").forEach(node => {
      node.textContent = "内置演示数据";
    });
    const title = document.querySelector("#page-overview h1");
    if (title) title.textContent = `${demo.project?.name || "内置项目"}（演示）`;
    renderLiveWorkflows(demo.jobs || []);
    const risks = document.querySelector("#page-overview .risk-list");
    if (risks) risks.innerHTML = (demo.risks || []).slice(0, 3).map(item => `<div class="risk ${item.severity === "high" ? "high" : ""}"><div class="risk-icon">!</div><div><strong>${escapeHtml(item.title || "演示风险")}</strong><p>${escapeHtml(item.detail || item.object || "")}</p></div></div>`).join("") || emptyState("暂无演示风险", "当前演示集没有风险项。");
  }
  function importStatus(item) {
    return String(item.run?.status || item.run_status || item.status || item.analysis_status || "unknown").toLowerCase();
  }
  function importSummary(item) {
    let summary = item.summary || item.analysis_summary || item.result?.summary || {};
    if ((!summary || typeof summary !== "object" || !Object.keys(summary).length) && item.summary_json) {
      try { summary = JSON.parse(item.summary_json); } catch (_) { summary = {}; }
    }
    const values = [
      ["表", summary.tables ?? summary.table_count],
      ["字段", summary.columns ?? summary.column_count],
      ["血缘", summary.lineage ?? summary.lineage_count ?? summary.edges],
      ["风险", summary.risks ?? summary.risk_count ?? summary.findings]
    ].filter(([, value]) => value != null);
    return values.length ? values.map(([label, value]) => `${label} ${Array.isArray(value) ? value.length : value}`).join(" · ") : "等待分析摘要";
  }
  function renderImportHistory(items = state.versions) {
    const rows = Array.isArray(items) ? items : [];
    const statuses = rows.map(importStatus);
    const pending = statuses.filter(status => ["queued", "running", "processing", "pending"].includes(status)).length;
    const completed = statuses.filter(status => status === "completed").length;
    const failed = statuses.filter(status => status === "failed").length;
    const cards = $("importHistorySummary");
    if (cards) {
      cards.innerHTML = [["全部版本", rows.length], ["处理中", pending], ["已完成", completed], ["失败", failed]]
        .map(([label, value]) => `<div class="card stat"><div class="label">${label}</div><div class="value">${value}</div></div>`)
        .join("");
    }
    const target = $("importHistoryRows");
    if (!target) return;
    target.innerHTML = rows.length ? rows.map(item => {
      const status = importStatus(item);
      const statusLabel = { queued: "排队中", running: "分析中", processing: "分析中", pending: "等待中", completed: "已完成", failed: "失败" }[status] || status;
      const fileCount = item.file_count ?? item.files_count ?? item.summary?.files ?? item.files?.length ?? "—";
      const error = item.error || item.run?.error || item.run_error || item.detail || "";
      return `<tr><td><div class="table-name">V${escapeHtml(item.version ?? item.id ?? "—")}</div><div class="table-desc mono">${escapeHtml(item.filename || item.file_name || "—")}</div></td><td><span class="health ${status === "completed" ? "ok" : status === "failed" ? "warn" : ""}">${escapeHtml(statusLabel)}</span></td><td>${escapeHtml(importSummary(item))}</td><td>${escapeHtml(fileCount)}</td><td><div>${escapeHtml(item.created_at || "—")}</div><div class="table-desc">${escapeHtml(item.completed_at || item.run?.completed_at || "—")}</div></td><td>${error ? `<div class="diagnostic error">× <span>${escapeHtml(typeof error === "string" ? error : JSON.stringify(error))}</span></div>` : '<span class="subtle">无错误</span>'}</td></tr>`;
    }).join("") : `<tr><td colspan="6">${emptyState("暂无导入历史", "点击“导入项目包”创建第一个分析版本。")}</td></tr>`;
    if (pending) scheduleImportHistoryRefresh();
  }
  function scheduleImportHistoryRefresh() {
    const generation = ++state.importHistoryPollGeneration;
    ctx.defer(() => {
      if (generation !== state.importHistoryPollGeneration || state.mode !== "live") return;
      refreshImportHistory({ schedule: true }).catch(error => {
        $("importHistoryRows").innerHTML = `<tr><td colspan="6">${emptyState("导入状态刷新失败", error.message)}</td></tr>`;
      });
    }, 2500);
  }
  async function enrichImportHistory(items) {
    return Promise.all((items || []).map(async item => {
      if (!item?.id) return item;
      try {
        const detail = await apis.imports.get(item.id);
        return { ...item, ...detail };
      } catch (_) {
        return item;
      }
    }));
  }
  async function refreshImportHistory({ schedule = false } = {}) {
    if (state.mode !== "live" || !state.projectId) {
      renderImportHistory([]);
      return [];
    }
    if (!schedule) state.importHistoryPollGeneration += 1;
    const payload = await apis.imports.list(state.projectId);
    const items = await enrichImportHistory(unwrap(payload, ["imports", "versions", "items", "data"]));
    state.versions = items;
    runtime.liveStore.replace({ ...runtime.liveStore.getSnapshot(), versions: items });
    updateVersions();
    renderImportHistory(items);
    return items;
  }
  async function refreshLineage() {
    if (state.mode !== "live" || !state.projectId) return;
    const mode = $("lineageMode")?.value === "字段级血缘" ? "column" : "table";
    const depthText = $("lineageDepth")?.value || "";
    const depth = depthText.includes("直接") ? 1 : depthText.includes("5") ? 5 : 3;
    const payload = await apis.lineage.get(state.projectId, { level: mode, depth });
    const rawNodes = unwrap(payload, ["nodes", "tables", "items"]);
    const rawEdges = unwrap(payload, ["edges", "lineage", "data"]);
    ui.setNodes(layoutNodes(rawNodes));
    ui.setEdges(rawEdges);
    ui.renderGraph();
    ui.focusHint(`${mode === "column" ? "字段级" : "表级"}血缘 · 上下游 ${depth} 层`);
  }
  function updateVersions() {
    const left = $("compareLeft");
    const right = $("compareRight");
    const button = $("runCompare");
    if (!state.versions.length) {
      left.innerHTML = '<option value="">暂无可比较版本</option>';
      right.innerHTML = '<option value="">暂无可比较版本</option>';
      left.disabled = true;
      right.disabled = true;
      button.disabled = true;
      return;
    }
    const options = state.versions.map(v => `<option value="${escapeHtml(v.version ?? v.id)}">${escapeHtml(v.version || v.note || v.created_at || v.id)}</option>`).join("");
    left.innerHTML = options;
    right.innerHTML = options;
    left.disabled = state.versions.length < 2;
    right.disabled = state.versions.length < 2;
    button.disabled = state.versions.length < 2;
    const values = new Set(state.versions.map(version => String(version.version ?? version.id)));
    if (state.routeLeftVersion && values.has(String(state.routeLeftVersion))) left.value = String(state.routeLeftVersion);
    else if (state.versions.length > 1) left.selectedIndex = 1;
    if (state.routeRightVersion && values.has(String(state.routeRightVersion))) right.value = String(state.routeRightVersion);
    else right.selectedIndex = 0;
    const leftOption = left.value;
    const rightOption = right.value;
    if (leftOption && rightOption) updateCompareMeta();
  }
  async function updateCompareMeta() {
    if (state.mode !== "live" || !state.versions.length) return;
    try {
      const left = await fetchImportMetaByVersion($("compareLeft").value);
      const right = await fetchImportMetaByVersion($("compareRight").value);
      renderCompareMeta(left, right);
    } catch (error) {
      $("compareVersionMeta").innerHTML = `<div class="diagnostic error">× <span>版本详情读取失败：${escapeHtml(error.message)}</span></div>`;
    }
  }
  function projectMode() {
    const checked = document.querySelector('input[name="projectMode"]:checked');
    return checked ? checked.value : "existing";
  }
  function selectedProjectName() {
    if (projectMode() === "new") return $("importProjectName").value.trim();
    const option = $("wizardProjectSelect").selectedOptions[0];
    return option ? option.textContent : "";
  }
  async function ensureProject() {
    if (projectMode() === "existing") {
      const id = $("wizardProjectSelect").value;
      if (!id) throw new Error("请选择现有项目，或改为创建新项目");
      state.projectId = id;
      $("projectSelect").value = String(id);
      return id;
    }
    const name = $("importProjectName").value.trim();
    if (!name) throw new Error("请填写新项目名称");
    if (state.mode !== "live") throw new Error("演示模式不能创建项目，请先连接真实后端");
    const result = await apis.projects.create({ name });
    const id = result.id || (result.project && result.project.id);
    if (!id) throw new Error("后端未返回新项目 ID");
    state.projectId = id;
    store.resetProject(id);
    router.update({ projectId: id, table: null, leftVersion: null, rightVersion: null, focus: null });
    await loadProjects();
    return id;
  }
  Object.assign(ctx, { ensureProject, loadProjectData, loadProjects, projectMode, refreshImportHistory, refreshLineage, renderDemoContent, renderImportHistory, renderLiveWorkflows, renderProjectLoadFailures, selectedProjectName, setProjectOptions, syncWizardProjects, updateCompareMeta, updateLiveSummaries, updateVersions });
}
