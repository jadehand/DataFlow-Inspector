export function installCore(ctx) {
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
  const downloadGuideFallback = (...args) => ctx.downloadGuideFallback(...args);
  const downloadText = (...args) => ctx.downloadText(...args);
  const ensureProject = (...args) => ctx.ensureProject(...args);
  const exportAssetDictionary = (...args) => ctx.exportAssetDictionary(...args);
  const exportCompareResult = (...args) => ctx.exportCompareResult(...args);
  const exportDetailJson = (...args) => ctx.exportDetailJson(...args);
  const exportSelectedAssets = (...args) => ctx.exportSelectedAssets(...args);
  const exportServerDictionary = (...args) => ctx.exportServerDictionary(...args);
  const fetchImportMetaByVersion = (...args) => ctx.fetchImportMetaByVersion(...args);
  const formatBytes = (...args) => ctx.formatBytes(...args);
  const loadDetailDiff = (...args) => ctx.loadDetailDiff(...args);
  const loadProjectData = (...args) => ctx.loadProjectData(...args);
  const loadProjects = (...args) => ctx.loadProjects(...args);
  const loadTableDetail = (...args) => ctx.loadTableDetail(...args);
  const nextWizardStep = (...args) => ctx.nextWizardStep(...args);
  const normalizePreflight = (...args) => ctx.normalizePreflight(...args);
  const openDetailForTable = (...args) => ctx.openDetailForTable(...args);
  const openMetadataPreview = (...args) => ctx.openMetadataPreview(...args);
  const openTableDrawer = (...args) => ctx.openTableDrawer(...args);
  const openWizard = (...args) => ctx.openWizard(...args);
  const prepareImpactContext = (...args) => ctx.prepareImpactContext(...args);
  const prepareImpactSeed = (...args) => ctx.prepareImpactSeed(...args);
  const projectMode = (...args) => ctx.projectMode(...args);
  const renderCompareMeta = (...args) => ctx.renderCompareMeta(...args);
  const renderCompareResult = (...args) => ctx.renderCompareResult(...args);
  const renderDemoContent = (...args) => ctx.renderDemoContent(...args);
  const renderDetailDiff = (...args) => ctx.renderDetailDiff(...args);
  const renderImpactEvidence = (...args) => ctx.renderImpactEvidence(...args);
  const renderImpactResult = (...args) => ctx.renderImpactResult(...args);
  const renderLiveWorkflows = (...args) => ctx.renderLiveWorkflows(...args);
  const renderMetadataPreview = (...args) => ctx.renderMetadataPreview(...args);
  const renderPackageTree = (...args) => ctx.renderPackageTree(...args);
  const renderPreflight = (...args) => ctx.renderPreflight(...args);
  const renderProjectLoadFailures = (...args) => ctx.renderProjectLoadFailures(...args);
  const renderTableDetail = (...args) => ctx.renderTableDetail(...args);
  const renderTablePreview = (...args) => ctx.renderTablePreview(...args);
  const renderTableStrategyOptions = (...args) => ctx.renderTableStrategyOptions(...args);
  const resetTableDrawer = (...args) => ctx.resetTableDrawer(...args);
  const resetWizard = (...args) => ctx.resetWizard(...args);
  const runBulkDraftEdit = (...args) => ctx.runBulkDraftEdit(...args);
  const runBulkImpactSeed = (...args) => ctx.runBulkImpactSeed(...args);
  const runComparison = (...args) => ctx.runComparison(...args);
  const runImpact = (...args) => ctx.runImpact(...args);
  const runPreflight = (...args) => ctx.runPreflight(...args);
  const runTableImport = (...args) => ctx.runTableImport(...args);
  const runTablePreview = (...args) => ctx.runTablePreview(...args);
  const saveDetailMetadata = (...args) => ctx.saveDetailMetadata(...args);
  const selectedAssets = (...args) => ctx.selectedAssets(...args);
  const selectedProjectName = (...args) => ctx.selectedProjectName(...args);
  const setProjectOptions = (...args) => ctx.setProjectOptions(...args);
  const setSelectedTable = (...args) => ctx.setSelectedTable(...args);
  const setWizardStep = (...args) => ctx.setWizardStep(...args);
  const showImportError = (...args) => ctx.showImportError(...args);
  const switchProject = (...args) => ctx.switchProject(...args);
  const syncDetailDraftHint = (...args) => ctx.syncDetailDraftHint(...args);
  const syncWizardProjects = (...args) => ctx.syncWizardProjects(...args);
  const tableDrawerStatus = (...args) => ctx.tableDrawerStatus(...args);
  const updateCompareMeta = (...args) => ctx.updateCompareMeta(...args);
  const updateLiveSummaries = (...args) => ctx.updateLiveSummaries(...args);
  const updateProjectMode = (...args) => ctx.updateProjectMode(...args);
  const updateVersions = (...args) => ctx.updateVersions(...args);
  const uploadZip = (...args) => ctx.uploadZip(...args);
  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
  }
  function resolveApiHref(path) {
    const text = String(path || "").trim();
    if (!text) return "#";
    if (/^https?:\/\//i.test(text)) return text;
    if (text.startsWith("/api/")) return apiOrigin + text;
    if (text.startsWith("/")) return apiRoot + text;
    return apiRoot + "/" + text.replace(/^\/+/, "");
  }
  function unwrap(value, keys) {
    if (Array.isArray(value)) return value;
    for (const key of keys) if (value && Array.isArray(value[key])) return value[key];
    return [];
  }
  function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
  async function waitForImport(importId, onProgress) {
    if (!importId) throw new Error("后端未返回导入批次 ID");
    for (let attempt = 0; attempt < 120; attempt += 1) {
      const result = await apis.imports.get(importId);
      const status = String(result?.status || "").toLowerCase();
      if (typeof onProgress === "function") onProgress(result, attempt);
      if (status === "completed") return result;
      if (status === "failed") {
        const detail = result?.error || result?.detail || result?.message || "导入分析失败";
        throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
      }
      await delay(1000);
    }
    throw new Error("导入分析等待超时，请稍后在导入历史中查看状态");
  }
  async function saveDictionaryBulk(payload) {
    if (!state.projectId) throw new Error("请先选择项目");
    return apis.dictionary.save(state.projectId, payload);
  }
  async function previewDictionaryBulk(payload) {
    if (!state.projectId) throw new Error("请先选择项目");
    return apis.dictionary.preview(state.projectId, payload);
  }
  async function fetchMetadataRevisions() {
    if (!state.projectId) return [];
    const payload = await apis.dictionary.revisions(state.projectId);
    state.metadataRevisions = payload.revisions || [];
    return state.metadataRevisions;
  }
  async function fetchMetadataCompare() {
    const revisions = state.metadataRevisions || [];
    if (revisions.length < 2) {
      state.metadataCompareResult = null;
      return null;
    }
    const left = revisions[1]?.revision;
    const right = revisions[0]?.revision;
    if (!left || !right) return null;
    const payload = await apis.compare.metadata(state.projectId, left, right);
    state.metadataCompareResult = payload;
    return payload;
  }
  function metadataRevisionPayload() {
    return {
      source: $("metadataRevisionSource")?.value.trim() || (state.metadataPreviewContext?.defaultSource || "detail_editor"),
      operator: $("metadataRevisionOperator")?.value.trim() || "",
      reason: $("metadataRevisionReason")?.value.trim() || ""
    };
  }
  function setMode(mode, message) {
    state.mode = mode;
    if (mode !== "demo") {
      state.importHistoryPollGeneration += 1;
      state.versions = [];
      runtime.liveStore.clear();
      ui.clearData();
      state.selectedAssets = [];
      state.selectedTableDetail = null;
      state.compareResult = null;
      state.impactSeed = null;
      ctx.updateVersions?.();
      ctx.renderImportHistory?.([]);
    }
    if (store && typeof store.setState === "function") {
      store.setState({ connectionMode: mode });
    }
    const pill = $("connectionPill"), banner = $("modeBanner");
    pill.className = "connection-pill" + (mode === "live" ? " live" : mode === "connecting" ? " loading" : "");
    pill.textContent = mode === "live" ? "真实数据" : mode === "demo" ? "演示数据" : mode === "error" ? "连接失败" : "连接中";
    $("apiEndpoint").textContent = apiRoot;
    banner.classList.toggle("show", mode === "demo" || mode === "error");
    $("modeBannerTitle").textContent = mode === "demo" ? "演示模式" : "后端连接失败";
    $("modeBannerText").textContent = mode === "demo"
      ? "当前明确展示内置样例；上传、分析与问答不会发送到后端。"
      : (message || "无法读取后端。页面不会自动把样例结果伪装成真实分析。");
    $("demoModeBtn").style.display = mode === "error" ? "" : "none";
    $("sideVersion").textContent = mode === "live" ? "真实分析服务已连接"
      : mode === "demo" ? "当前使用演示数据"
      : mode === "error" ? "分析服务连接失败" : "正在连接分析服务…";
    if (mode !== "demo") resetLiveOnlyContent();
  }
  function emptyState(title, detail) {
    return `<div class="empty-shell"><strong>${escapeHtml(title)}</strong>${escapeHtml(detail)}</div>`;
  }
  function resetLiveOnlyContent() {
    document.querySelectorAll("#page-overview .stat .value").forEach(node => { node.textContent = "0"; });
    document.querySelectorAll("#page-overview .stat .delta").forEach(node => { node.textContent = "等待真实分析结果"; });
    const overviewFlows = document.querySelector("#page-overview .flow-list");
    const overviewRisks = document.querySelector("#page-overview .risk-list");
    if (overviewFlows) overviewFlows.innerHTML = emptyState("暂无作业流", "导入并完成真实分析后展示作业。");
    if (overviewRisks) overviewRisks.innerHTML = emptyState("暂无风险结果", "完成真实分析后展示质量发现。");
    const workflow = document.querySelector("#page-workflow .workflow-canvas");
    if (workflow) workflow.innerHTML = emptyState("暂无作业流", "当前项目尚未生成真实作业关系。");
    $("evidenceTitle").textContent = "尚未选择血缘节点";
    $("evidenceDesc").textContent = "选择真实血缘节点后展示其说明。";
    ["evidenceGrain", "evidenceScript", "evidenceRelation"].forEach(id => {
      const node = $(id);
      if (node) node.textContent = "—";
    });
    $("impactResult").classList.remove("show");
    $("messages").innerHTML = emptyState("暂无对话", "输入问题后将调用真实项目助手。");
  }
  function normalizeTable(t) {
    const columns = t.columns || t.fields || [];
    const upstream = t.upstream_count ?? (t.upstream || []).length;
    const downstream = t.downstream_count ?? (t.downstream || []).length;
    return {
      name: escapeHtml(t.qualified_name || t.qualifiedName || t.full_name || t.name),
      desc: escapeHtml(t.description || t.comment || ""),
      layer: String(t.layer || "OTHER").toUpperCase(),
      grain: escapeHtml(t.grain || t.data_grain || "待识别"),
      time: escapeHtml(t.time_field || t.timeField || t.primary_time_column || "—"),
      fields: t.column_count ?? columns.length,
      relation: upstream + " / " + downstream,
      risk: Boolean(t.risk || t.has_risk || t.status === "warning"),
      database: escapeHtml(t.database || "—"),
      displayName: escapeHtml(t.display_name || t.business_name || t.alias || ""),
      flow: escapeHtml(t.flow || t.business_line || ""),
      partition: escapeHtml(t.partition || t.partition_desc || "—"),
      upstream: escapeHtml(t.upstream_display || "—"),
      etl: escapeHtml(t.etl_path || t.sql_path || "—"),
      ddl: escapeHtml(t.ddl_file || "—"),
      owner: escapeHtml(t.owner || "待补充"),
      frequency: escapeHtml(t.frequency || "频率待补充"),
      retention: escapeHtml(t.retention || "留存待补充"),
      note: escapeHtml(t.note || t.remark || "")
    };
  }
  function normalizeMetric(m) {
    return {
      name: escapeHtml(m.display_name || m.business_name || m.name || m.field_name || "未命名指标"),
      code: escapeHtml(m.field_name || m.code || m.name || "—"),
      formula: escapeHtml(m.formula || m.expression || m.sql_expression || "—"),
      grain: escapeHtml(Array.isArray(m.time_grain || m.grain) ? (m.time_grain || m.grain).join(" + ") : (m.time_grain || m.grain || "待识别")),
      status: m.confirmed === false || m.status === "inferred" ? "待确认" : "已确认",
      consumers: Array.isArray(m.consumers) ? m.consumers.length : (m.consumer_count ?? null)
    };
  }
  function normalizeNode(n, index) {
    const layer = String(n.layer || n.table_layer || "OTHER").toUpperCase();
    const lane = {SOURCE:0,RDS:0,ODS:1,DWD:2,DIM:2,DWS:3,ADS:4}[layer] ?? 2;
    const inLane = index;
    return {
      id: n.qualified_name || n.qualifiedName || n.name || n.id || n.table_id,
      x: 8 + lane * 152,
      y: 45 + inLane * 150,
      n: escapeHtml(n.qualified_name || n.qualifiedName || n.name),
      l: layer === "RDS" ? "SOURCE" : layer,
      d: escapeHtml(n.description || n.desc || "数据资产"),
      grain: escapeHtml(n.grain || n.data_grain || "—"),
      script: escapeHtml(n.sql_path || n.etl_path || n.file || "—"),
      relation: escapeHtml(n.relation || n.expression || n.operation || "—")
    };
  }
  function layoutNodes(rawNodes) {
    const laneCounts = new Map();
    return (rawNodes || []).slice(0, 20).map(node => {
      const layer = String(node.layer || node.table_layer || "OTHER").toUpperCase();
      const lane = {SOURCE:0,RDS:0,ODS:1,DWD:2,DIM:2,DWS:3,ADS:4}[layer] ?? 2;
      const indexInLane = laneCounts.get(lane) || 0;
      laneCounts.set(lane, indexInLane + 1);
      return normalizeNode(node, indexInLane);
    });
  }
  function tagColor(kind) {
    return {
      metric: "var(--success)",
      time: "var(--warning)",
      partition: "var(--accent)",
      dimension: "var(--ods)",
      field: "#55718c"
    }[kind] || "#55718c";
  }
  function unique(list) {
    return [...new Set((list || []).filter(Boolean))];
  }
  function inferFlowFromPath(path, projectName) {
    const normalized = String(path || "").replace(/\\/g, "/");
    const nested = normalized.match(/(?:sql|ddl)\/([^/]+)\/[^/]+$/i);
    if (nested && nested[1]) return nested[1];
    return projectName || "默认链路";
  }
  function enrichTables(tableList, lineageEdges, jobs, findings) {
    const project = state.projects.find(item => String(item.id) === String(state.projectId));
    const projectName = project ? (project.name || project.project_name || "当前项目") : "当前项目";
    const riskObjects = new Set((findings || []).map(item => String(item.object || item.file || "").toLowerCase()));
    const upstreamMap = new Map();
    const fileMap = new Map();
    (lineageEdges || []).forEach(edge => {
      const target = String(edge.target || "");
      if (!upstreamMap.has(target)) upstreamMap.set(target, []);
      upstreamMap.get(target).push(String(edge.source || ""));
      if (edge.file) {
        if (!fileMap.has(target)) fileMap.set(target, []);
        fileMap.get(target).push(String(edge.file));
      }
    });
    const jobMap = new Map();
    (jobs || []).forEach(job => {
      const key = String(job.output_table || job.target_table || job.table_name || "").toLowerCase();
      if (key) jobMap.set(key, job);
    });
    return tableList.map(table => {
      const tableName = String(table.name || table.qualified_name || "");
      const tableKey = tableName.toLowerCase();
      const parts = tableName.split(".");
      const job = jobMap.get(tableKey) || {};
      const dws = table.dws || {};
      const files = unique([...(fileMap.get(tableName) || []), job.script_path, job.file]);
      const upstreams = unique(upstreamMap.get(tableName) || []);
      const risk = Boolean(
        table.risk || table.has_risk || riskObjects.has(tableKey) ||
        files.some(path => riskObjects.has(String(path).toLowerCase()))
      );
      const flow = table.business_line || inferFlowFromPath(files[0] || table.ddl_file || "", projectName);
      return Object.assign({}, table, {
        database: parts.length > 1 ? parts.slice(0, -1).join(".") : "default",
        display_name: table.display_name || table.comment || table.description || "",
        flow,
        partition: dws.partition_columns && dws.partition_columns.length
          ? `${dws.partition_type || "PARTITION"}(${dws.partition_columns.join(", ")})`
          : "未识别",
        upstream_display: upstreams.length ? upstreams.slice(0, 3).join(", ") : "无",
        etl_path: files[0] || "待补录",
        owner: table.owner || job.owner || "待补充",
        frequency: table.frequency || job.schedule || "待补充",
        retention: table.retention || "待补充",
        note: table.remark || table.description || "",
        risk,
        upstream_count: upstreams.length,
        downstream_count: table.downstream_count ?? 0,
      });
    });
  }
  function renderAssetFlowOptions(tableList) {
    const select = $("assetFlowFilter");
    if (!select) return;
    const current = select.value;
    const flows = unique((tableList || []).map(item => item.flow || item.business_line));
    select.innerHTML = `<option value="">全部业务线</option>${flows.map(flow => `<option value="${escapeHtml(flow)}">${escapeHtml(flow)}</option>`).join("")}`;
    if (flows.includes(current)) select.value = current;
  }
  Object.assign(ctx, { delay, emptyState, enrichTables, escapeHtml, fetchMetadataCompare, fetchMetadataRevisions, inferFlowFromPath, layoutNodes, metadataRevisionPayload, normalizeMetric, normalizeNode, normalizeTable, previewDictionaryBulk, renderAssetFlowOptions, resetLiveOnlyContent, resolveApiHref, saveDictionaryBulk, setMode, tagColor, unique, unwrap, waitForImport });
}
