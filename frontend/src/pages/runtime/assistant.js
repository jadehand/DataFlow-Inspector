export function installAssistant(ctx) {
  const { state, $, ui, apis, store, router, runtime, config, apiRoot, apiOrigin, tableStrategyLabels } = ctx;
  const allAssets = (...args) => ctx.allAssets(...args);
  const analysisSummary = (...args) => ctx.analysisSummary(...args);
  const bindDetailEditors = (...args) => ctx.bindDetailEditors(...args);
  const clearProjectDerivedState = (...args) => ctx.clearProjectDerivedState(...args);
  const closeMetadataPreview = (...args) => ctx.closeMetadataPreview(...args);
  const closeTableDrawer = (...args) => ctx.closeTableDrawer(...args);
  const collectDetailDraftPayload = (...args) => ctx.collectDetailDraftPayload(...args);
  const csvLine = (...args) => ctx.csvLine(...args);
  const delay = (...args) => ctx.delay(...args);
  const downloadText = (...args) => ctx.downloadText(...args);
  const emptyState = (...args) => ctx.emptyState(...args);
  const enrichTables = (...args) => ctx.enrichTables(...args);
  const ensureProject = (...args) => ctx.ensureProject(...args);
  const escapeHtml = (...args) => ctx.escapeHtml(...args);
  const exportAssetDictionary = (...args) => ctx.exportAssetDictionary(...args);
  const exportSelectedAssets = (...args) => ctx.exportSelectedAssets(...args);
  const exportServerDictionary = (...args) => ctx.exportServerDictionary(...args);
  const fetchImportMetaByVersion = (...args) => ctx.fetchImportMetaByVersion(...args);
  const fetchMetadataCompare = (...args) => ctx.fetchMetadataCompare(...args);
  const fetchMetadataRevisions = (...args) => ctx.fetchMetadataRevisions(...args);
  const inferFlowFromPath = (...args) => ctx.inferFlowFromPath(...args);
  const layoutNodes = (...args) => ctx.layoutNodes(...args);
  const loadDetailDiff = (...args) => ctx.loadDetailDiff(...args);
  const loadProjectData = (...args) => ctx.loadProjectData(...args);
  const loadProjects = (...args) => ctx.loadProjects(...args);
  const loadTableDetail = (...args) => ctx.loadTableDetail(...args);
  const metadataRevisionPayload = (...args) => ctx.metadataRevisionPayload(...args);
  const normalizeMetric = (...args) => ctx.normalizeMetric(...args);
  const normalizeNode = (...args) => ctx.normalizeNode(...args);
  const normalizePreflight = (...args) => ctx.normalizePreflight(...args);
  const normalizeTable = (...args) => ctx.normalizeTable(...args);
  const openDetailForTable = (...args) => ctx.openDetailForTable(...args);
  const openMetadataPreview = (...args) => ctx.openMetadataPreview(...args);
  const openTableDrawer = (...args) => ctx.openTableDrawer(...args);
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
  const renderPreflight = (...args) => ctx.renderPreflight(...args);
  const renderProjectLoadFailures = (...args) => ctx.renderProjectLoadFailures(...args);
  const renderTableDetail = (...args) => ctx.renderTableDetail(...args);
  const renderTablePreview = (...args) => ctx.renderTablePreview(...args);
  const renderTableStrategyOptions = (...args) => ctx.renderTableStrategyOptions(...args);
  const resetLiveOnlyContent = (...args) => ctx.resetLiveOnlyContent(...args);
  const resetTableDrawer = (...args) => ctx.resetTableDrawer(...args);
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
  const selectedProjectName = (...args) => ctx.selectedProjectName(...args);
  const setMode = (...args) => ctx.setMode(...args);
  const setProjectOptions = (...args) => ctx.setProjectOptions(...args);
  const setSelectedTable = (...args) => ctx.setSelectedTable(...args);
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
  const updateVersions = (...args) => ctx.updateVersions(...args);
  const uploadZip = (...args) => ctx.uploadZip(...args);
  const waitForImport = (...args) => ctx.waitForImport(...args);
  function exportDetailJson() {
    if (!state.selectedTableDetail) return ui.showToast("请先打开一张真实表详情");
    downloadText(`${(state.selectedTableName || "table-detail").replace(/[^\w.-]+/g, "_")}.json`, JSON.stringify(state.selectedTableDetail, null, 2), "application/json;charset=utf-8");
  }
  function exportCompareResult() {
    if (!state.compareResult) return ui.showToast("请先执行版本比较");
    downloadText(`compare-${$("compareLeft").value}-to-${$("compareRight").value}.json`, JSON.stringify(state.compareResult, null, 2), "application/json;charset=utf-8");
  }
  async function ask(question) {
    const messages = $("messages");
    messages.insertAdjacentHTML("beforeend", `<div class="msg user">${escapeHtml(question)}</div>`);
    if (state.mode !== "live") {
      messages.insertAdjacentHTML("beforeend", '<div class="msg ai"><div class="avatar">✦</div><div class="bubble"><strong>演示回答</strong>：当前未连接后端，此回答仅展示交互形态，不代表对真实 SQL 的分析。</div></div>');
      messages.scrollTop = messages.scrollHeight; return;
    }
    try {
      const answer = await apis.assistant.ask(state.projectId, question);
      messages.insertAdjacentHTML("beforeend", `<div class="msg ai"><div class="avatar">✦</div><div class="bubble">${escapeHtml(answer.answer || answer.message || JSON.stringify(answer))}</div></div>`);
    } catch (error) {
      messages.insertAdjacentHTML("beforeend", `<div class="msg ai"><div class="avatar">!</div><div class="bubble" style="color:var(--danger)">真实问答失败：${escapeHtml(error.message)}</div></div>`);
    }
    messages.scrollTop = messages.scrollHeight;
  }

  const packageTrees = {
    minimum: `token-traffic/
├── ddl/                         [推荐]
│   └── all_tables.sql           [推荐]
└── sql/                         [必需]
    ├── 01_ods_to_dwd.sql        [必需]
    └── 02_dwd_to_dws.sql        [必需]`,
    recommended: `token-traffic/
├── manifest.yaml                [推荐]
├── ddl/                         [推荐]
│   ├── 01_ods.sql
│   ├── 02_dwd.sql
│   ├── 03_dimensions.sql
│   ├── 04_dws.sql
│   └── 05_ads.sql
├── sql/                         [必需]
│   ├── 01_rds_to_ods.sql
│   ├── 02_ods_to_dwd.sql
│   ├── 03_dwd_enrichment.sql
│   ├── 04_dws_minute.sql
│   ├── 05_dws_hour.sql
│   └── 06_ads_report.sql
├── metadata/
│   └── jobs.csv                 [推荐]
└── samples/                     [可选]
    ├── ods_token_request.csv
    └── dwd_token_request.csv`
  };
  function renderPackageTree(type) {
    $("packageTree").textContent = packageTrees[type];
    document.querySelectorAll(".package-tab").forEach(button => button.classList.toggle("active", button.dataset.package === type));
  }
  function setWizardStep(step) {
    state.wizardStep = step;
    document.querySelectorAll("[data-wpanel]").forEach(panel => panel.classList.toggle("active", Number(panel.dataset.wpanel) === step));
    document.querySelectorAll("[data-wstep]").forEach(item => {
      const value = Number(item.dataset.wstep);
      item.classList.toggle("active", value === step);
      item.classList.toggle("done", value < step);
    });
    $("wizardBack").hidden = step === 1;
    $("wizardNext").hidden = false;
    $("wizardNext").disabled = false;
    $("wizardNext").textContent = step === 3 ? "检查项目包" : step === 4 ? "上传并分析" : "下一步";
    if (step === 4) {
      $("confirmProject").textContent = selectedProjectName() || "—";
      $("confirmFile").textContent = $("importFile").files[0]?.name || "—";
      $("confirmPreflight").textContent = state.preflight ? "真实预检通过" : "未完成";
      $("confirmNote").textContent = $("importVersionNote").value.trim() || "无";
      $("wizardNext").disabled = !state.preflight;
    }
    const active = document.querySelector(`[data-wpanel="${step}"]`);
    const focusable = active && active.querySelector("input:not([hidden]),select,button");
    if (focusable) setTimeout(() => focusable.focus(), 0);
  }
  function resetWizard() {
    state.preflight = null; state.importResult = null;
    $("importComplete").hidden = true; $("importConfirm").hidden = false;
    $("importProgress").classList.remove("show");
    $("preflightArea").innerHTML = '<div class="load-state"><strong>尚未执行预检</strong>选择文件后，点击“检查项目包”。</div>';
    $("fileMeta").classList.toggle("show", Boolean($("importFile").files[0]));
    $("wizardCancel").textContent = "取消";
    syncWizardProjects();
    if (!state.projects.length) {
      const radio = document.querySelector('input[name="projectMode"][value="new"]');
      radio.checked = true;
    }
    updateProjectMode();
    setWizardStep(1);
  }
  function openWizard() {
    resetWizard();
    $("wizardMode").className = "wizard-mode" + (state.mode === "live" ? " live" : "");
    $("wizardMode").textContent = state.mode === "live" ? "● 真实后端：文件会执行预检与分析"
      : state.mode === "demo" ? "演示模式：不会上传或生成真实结果" : "后端未连接：只能查看导入要求";
    $("drawer").classList.add("open");
  }
  function closeWizard() {
    $("drawer").classList.remove("open");
    $("importBtn").focus();
  }
  function updateProjectMode() {
    const isNew = projectMode() === "new";
    $("existingProjectField").hidden = isNew;
    $("newProjectField").hidden = !isNew;
  }
  function formatBytes(bytes) {
    if (!Number.isFinite(bytes)) return "—";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
  }
  function downloadGuideFallback() {
    const content = `DataFlow Inspector 空白项目模板

请按以下目录创建文件后，将 token-traffic 整个目录压缩为 ZIP：

${packageTrees.recommended}

manifest.yaml 示例：
project: token_traffic
sql_dialect: gaussdb_dws
timezone: Asia/Shanghai
`;
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([content], {type:"text/plain;charset=utf-8"}));
    link.download = "dataflow-import-template.txt";
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  }
  async function nextWizardStep() {
    try {
      if (state.wizardStep === 1) {
        if (projectMode() === "existing" && !$("wizardProjectSelect").value) throw new Error("请选择现有项目，或改为创建新项目");
        if (projectMode() === "new" && !$("importProjectName").value.trim()) throw new Error("请填写新项目名称");
        setWizardStep(2);
      } else if (state.wizardStep === 2) {
        setWizardStep(3);
      } else if (state.wizardStep === 3) {
        $("wizardNext").disabled = true; $("wizardNext").textContent = "检查中…";
        await runPreflight();
        setWizardStep(4);
      } else {
        $("wizardNext").disabled = true; $("wizardNext").textContent = "分析中…";
        await uploadZip();
      }
    } catch (error) {
      ui.showToast(error.message);
      $("wizardNext").disabled = false;
      $("wizardNext").textContent = state.wizardStep === 3 ? "检查项目包" : state.wizardStep === 4 ? "上传并分析" : "下一步";
    }
  }
  Object.assign(ctx, { ask, closeWizard, downloadGuideFallback, exportCompareResult, exportDetailJson, formatBytes, nextWizardStep, openWizard, renderPackageTree, resetWizard, setWizardStep, updateProjectMode });
}
