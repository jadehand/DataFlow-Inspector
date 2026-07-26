export function installCatalog(ctx) {
  const { state, $, ui, apis, store, router, runtime, config, apiRoot, apiOrigin, tableStrategyLabels } = ctx;
  const analysisSummary = (...args) => ctx.analysisSummary(...args);
  const ask = (...args) => ctx.ask(...args);
  const closeTableDrawer = (...args) => ctx.closeTableDrawer(...args);
  const closeWizard = (...args) => ctx.closeWizard(...args);
  const delay = (...args) => ctx.delay(...args);
  const downloadGuideFallback = (...args) => ctx.downloadGuideFallback(...args);
  const emptyState = (...args) => ctx.emptyState(...args);
  const enrichTables = (...args) => ctx.enrichTables(...args);
  const ensureProject = (...args) => ctx.ensureProject(...args);
  const escapeHtml = (...args) => ctx.escapeHtml(...args);
  const exportAssetDictionary = (...args) => ctx.exportAssetDictionary(...args);
  const exportCompareResult = (...args) => ctx.exportCompareResult(...args);
  const exportDetailJson = (...args) => ctx.exportDetailJson(...args);
  const exportSelectedAssets = (...args) => ctx.exportSelectedAssets(...args);
  const exportServerDictionary = (...args) => ctx.exportServerDictionary(...args);
  const fetchMetadataCompare = (...args) => ctx.fetchMetadataCompare(...args);
  const fetchMetadataRevisions = (...args) => ctx.fetchMetadataRevisions(...args);
  const formatBytes = (...args) => ctx.formatBytes(...args);
  const inferFlowFromPath = (...args) => ctx.inferFlowFromPath(...args);
  const layoutNodes = (...args) => ctx.layoutNodes(...args);
  const loadProjectData = (...args) => ctx.loadProjectData(...args);
  const loadProjects = (...args) => ctx.loadProjects(...args);
  const metadataRevisionPayload = (...args) => ctx.metadataRevisionPayload(...args);
  const nextWizardStep = (...args) => ctx.nextWizardStep(...args);
  const normalizeMetric = (...args) => ctx.normalizeMetric(...args);
  const normalizeNode = (...args) => ctx.normalizeNode(...args);
  const normalizePreflight = (...args) => ctx.normalizePreflight(...args);
  const normalizeTable = (...args) => ctx.normalizeTable(...args);
  const openDetailForTable = (...args) => ctx.openDetailForTable(...args);
  const openTableDrawer = (...args) => ctx.openTableDrawer(...args);
  const openWizard = (...args) => ctx.openWizard(...args);
  const prepareImpactContext = (...args) => ctx.prepareImpactContext(...args);
  const prepareImpactSeed = (...args) => ctx.prepareImpactSeed(...args);
  const previewDictionaryBulk = (...args) => ctx.previewDictionaryBulk(...args);
  const projectMode = (...args) => ctx.projectMode(...args);
  const renderAssetFlowOptions = (...args) => ctx.renderAssetFlowOptions(...args);
  const renderDemoContent = (...args) => ctx.renderDemoContent(...args);
  const renderImpactEvidence = (...args) => ctx.renderImpactEvidence(...args);
  const renderImpactResult = (...args) => ctx.renderImpactResult(...args);
  const renderLiveWorkflows = (...args) => ctx.renderLiveWorkflows(...args);
  const renderPackageTree = (...args) => ctx.renderPackageTree(...args);
  const renderPreflight = (...args) => ctx.renderPreflight(...args);
  const renderProjectLoadFailures = (...args) => ctx.renderProjectLoadFailures(...args);
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
  const saveDictionaryBulk = (...args) => ctx.saveDictionaryBulk(...args);
  const selectedProjectName = (...args) => ctx.selectedProjectName(...args);
  const setMode = (...args) => ctx.setMode(...args);
  const setProjectOptions = (...args) => ctx.setProjectOptions(...args);
  const setWizardStep = (...args) => ctx.setWizardStep(...args);
  const showImportError = (...args) => ctx.showImportError(...args);
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
  async function fetchImportMetaByVersion(versionValue) {
    const version = state.versions.find(item => String(item.version ?? item.id) === String(versionValue));
    if (!version || !version.id) return null;
    if (state.selectedVersionMeta[version.id]) return state.selectedVersionMeta[version.id];
    const detail = await apis.imports.get(version.id);
    state.selectedVersionMeta[version.id] = detail;
    return detail;
  }
  function renderCompareMeta(leftMeta, rightMeta) {
    const container = $("compareVersionMeta");
    if (!container) return;
    const latestRevision = state.metadataRevisions[0] || null;
    const panel = meta => {
      if (!meta) return '<div class="load-state"><strong>版本详情暂不可用</strong>无法读取导入诊断。</div>';
      const warnings = (meta.diagnostics || []).filter(item => item.severity !== "error").slice(0, 2);
      const errors = (meta.diagnostics || []).filter(item => item.severity === "error").slice(0, 2);
      return `<div class="card" style="padding:14px">
        <div class="section-head"><h2>版本 ${escapeHtml(meta.version)}</h2><span class="health ${errors.length ? "warn" : "ok"}">${escapeHtml(meta.status || "completed")}</span></div>
        <div class="table-desc mono">${escapeHtml(meta.filename || "—")}</div>
        <div class="table-desc">表 ${escapeHtml(meta.summary?.tables ?? 0)} · 字段 ${escapeHtml(meta.summary?.columns ?? 0)} · 风险 ${escapeHtml(meta.summary?.risks ?? 0)}</div>
        ${errors.map(item => `<div class="diagnostic error">× <span>${escapeHtml(item.message || item.detail || "错误")}</span></div>`).join("")}
        ${warnings.map(item => `<div class="diagnostic warning">! <span>${escapeHtml(item.message || item.detail || "提示")}</span></div>`).join("") || '<div class="table-desc">无额外诊断。</div>'}
      </div>`;
    };
    const metadataCompare = state.metadataCompareResult;
    const metadataCard = metadataCompare
      ? `<div class="card" style="padding:14px;margin-top:12px"><div class="eyebrow">Metadata revision diff</div><h3>R${escapeHtml(metadataCompare.left_revision?.revision)} → R${escapeHtml(metadataCompare.right_revision?.revision)}</h3><p class="subtle">表级变更 ${escapeHtml(metadataCompare.summary?.table_changes || 0)}，字段级变更 ${escapeHtml(metadataCompare.summary?.column_changes || 0)}。</p><p class="table-desc">最新修订来源：${escapeHtml(metadataCompare.right_revision?.source || "—")} · 操作人：${escapeHtml(metadataCompare.right_revision?.operator || "—")}</p>${metadataCompare.right_revision?.reason ? `<p class="table-desc">原因：${escapeHtml(metadataCompare.right_revision.reason)}</p>` : ""}</div>`
      : `<div class="card" style="padding:14px;margin-top:12px"><div class="eyebrow">Metadata revision</div><h3>${latestRevision ? `当前 R${escapeHtml(latestRevision.revision)}` : "尚未形成元数据修订"}</h3><p class="subtle">${latestRevision ? `基于分析版本 ${escapeHtml(latestRevision.import_version || "—")} 生成，时间 ${escapeHtml(latestRevision.created_at || "—")}` : "当保存表级或字段级元数据后，这里会出现修订记录。"}</p>${latestRevision ? `<p class="table-desc">来源：${escapeHtml(latestRevision.source || "—")} · 操作人：${escapeHtml(latestRevision.operator || "—")}</p>${latestRevision.reason ? `<p class="table-desc">原因：${escapeHtml(latestRevision.reason)}</p>` : ""}` : ""}</div>`;
    container.innerHTML = `<div class="section-head"><h2>版本摘要与诊断</h2><span class="subtle" style="font-size:11px">导入历史 / 日志收口</span></div><div class="grid two">${panel(leftMeta)}${panel(rightMeta)}</div>${metadataCard}`;
  }
  function closeMetadataPreview(confirmed) {
    $("metadataPreviewDrawer").classList.remove("open");
    const resolver = state.metadataPreviewResolver;
    state.metadataPreviewResolver = null;
    if (resolver) resolver(Boolean(confirmed));
  }
  function renderMetadataPreview(preview, title) {
    const summary = preview?.summary || {};
    const revision = preview?.metadata_revision?.revision;
    const nextRevision = preview?.next_metadata_revision || ((revision || 0) + 1);
    const context = state.metadataPreviewContext || {};
    $("metadataPreviewTitle").textContent = title || "保存前变更预览";
    $("metadataPreviewLead").textContent = revision
      ? `当前元数据修订为 R${revision}，确认后将生成 R${nextRevision}。`
      : `当前还没有元数据修订记录，确认后将生成 R${nextRevision}。`;
    $("metadataRevisionSource").value = context.defaultSource || "detail_editor";
    $("metadataRevisionOperator").value = context.operator || "";
    $("metadataRevisionReason").value = context.reason || "";
    $("metadataPreviewSummary").innerHTML = [
      ["表更新", summary.table_updates || 0],
      ["字段更新", summary.column_updates || 0],
      ["表级差异", summary.table_field_changes || 0],
      ["字段差异", summary.column_field_changes || 0]
    ].map(item => `<div class="card stat" style="--tint:#eef5f7"><div class="label">${item[0]}</div><div class="value">${escapeHtml(item[1])}</div></div>`).join("");
    const tableChanges = (preview?.changes?.tables || []).map(item => `<div class="diff-card"><strong class="mono">${escapeHtml(item.table_name)}</strong><ul>${Object.entries(item.changes || {}).map(([key, value]) => `<li>${escapeHtml(key)}：${escapeHtml(value.before || "—")} → ${escapeHtml(value.after || "—")}</li>`).join("")}</ul></div>`);
    const columnChanges = (preview?.changes?.columns || []).map(item => `<div class="diff-card"><strong class="mono">${escapeHtml(item.table_name)}.${escapeHtml(item.column_name)}</strong><ul>${Object.entries(item.changes || {}).map(([key, value]) => `<li>${escapeHtml(key)}：${escapeHtml(value.before || "—")} → ${escapeHtml(value.after || "—")}</li>`).join("")}</ul></div>`);
    $("metadataPreviewBody").innerHTML = (tableChanges.length || columnChanges.length)
      ? `<div class="diff-grid">${tableChanges.join("")}${columnChanges.join("")}</div>`
      : '<div class="load-state"><strong>没有实际差异</strong>当前提交内容与已保存元数据一致。</div>';
  }
  function openMetadataPreview(preview, title) {
    renderMetadataPreview(preview, title);
    $("metadataPreviewDrawer").classList.add("open");
    return new Promise(resolve => { state.metadataPreviewResolver = resolve; });
  }
  function downloadText(filename, content, type) {
    const blob = new Blob([content], {type: type || "text/plain;charset=utf-8"});
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  }
  function csvLine(values) {
    return values.map(value => {
      const text = String(value ?? "");
      return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
    }).join(",");
  }
  function selectedAssets() {
    return typeof ui.getSelectedTables === "function" ? ui.getSelectedTables() : [];
  }
  function allAssets() {
    return typeof ui.getTables === "function" ? ui.getTables() : [];
  }
  function renderDetailDiff(comparePayload) {
    const container = $("detailDiff");
    const tableName = state.selectedTableName;
    const changed = comparePayload
      ? {
          table: comparePayload.table_name,
          columns: comparePayload.columns || {},
          metrics: comparePayload.metrics || {},
          structure: comparePayload.structure || {}
        }
      : (state.compareResult?.tables?.changed || []).find(item => item.table === tableName);
    if (!changed) {
      container.innerHTML = '<div class="empty-shell"><strong>暂无差异摘要</strong>当前表未出现在最近一次版本比较的变更集中。</div>';
      return;
    }
    const columnChanges = changed.columns || {};
    const sections = [
      ["新增字段", columnChanges.added || [], item => item.name || item],
      ["删除字段", columnChanges.removed || [], item => item.name || item],
      ["属性变化", columnChanges.changed || [], item => `${item.name || "字段"}：${Object.keys(item.changes || {}).join("、") || "属性变化"}`]
    ].filter(section => section[1].length);
    const structureChanges = Object.entries(changed.structure || {}).map(([key, value]) => `${key}：${JSON.stringify(value.before)} → ${JSON.stringify(value.after)}`);
    container.innerHTML = `<div class="diff-grid">${sections.map(section => `<div class="diff-card"><strong>${section[0]}</strong><ul>${section[1].slice(0, 6).map(item => `<li>${escapeHtml(section[2](item))}</li>`).join("")}</ul></div>`).join("")}${structureChanges.length ? `<div class="diff-card"><strong>结构调整</strong><ul>${structureChanges.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div>` : ""}<div class="download-row"><button class="btn primary" id="detailDiffImpactBtn">把本表变更带入影响分析</button></div></div>`;
    const impactBtn = $("detailDiffImpactBtn");
    if (impactBtn) impactBtn.onclick = () => {
      const firstChanged = (columnChanges.changed || [])[0];
      const firstAdded = (columnChanges.added || [])[0];
      const firstRemoved = (columnChanges.removed || [])[0];
      const target = firstChanged?.name || firstAdded?.name || firstRemoved?.name || tableName;
      const delta = firstChanged?.changes?.type || firstChanged?.changes?.formula || firstChanged?.changes?.grain || {};
      prepareImpactContext({
        object: target.includes(".") ? target : `${tableName}.${target}`,
        changeType: firstAdded ? "新增字段" : firstRemoved ? "字段类型变化" : "加工逻辑变化",
        before: delta.before || "—",
        after: delta.after || "—",
        context: `来自版本比较：${tableName}`
      });
      prepareImpactSeed({
        compare_scope: "project",
        left_version: Number($("compareLeft").value),
        right_version: Number($("compareRight").value)
      });
      ui.navigate("impact");
    };
  }
  async function loadDetailDiff(name) {
    if (!state.projectId || state.mode !== "live") return;
    const projectId = state.projectId;
    const generation = store.getState().requestGeneration;
    if (state.versions.length < 2) {
      $("detailDiff").innerHTML = '<div class="empty-shell"><strong>暂无差异摘要</strong>当前项目不足两个分析版本。</div>';
      return;
    }
    const left = state.versions[1]?.id;
    const right = state.versions[0]?.id;
    if (!left || !right) return renderDetailDiff();
    try {
      const result = await apis.detail.compare(state.projectId, name, left, right);
      if (projectId !== state.projectId || generation !== store.getState().requestGeneration) return;
      renderDetailDiff(result);
    } catch (_) {
      renderDetailDiff();
    }
  }
  function setSelectedTable(name) {
    state.selectedTableName = name || null;
    store.setState({ table: state.selectedTableName });
  }
  function clearProjectDerivedState() {
    Object.assign(state, {
      versions: [],
      selectedTableName: null,
      selectedTableDetail: null,
      detailDraft: null,
      compareResult: null,
      metadataCompareResult: null,
      selectedVersionMeta: {},
      selectedAssets: [],
      metadataRevisions: [],
      impactSeed: null
    });
    runtime.liveStore.clear();
    ui.setTables([]);
    ui.setMetrics([]);
    ui.setNodes([]);
    ui.setEdges([]);
    ui.renderAssets();
    ui.renderMetrics();
    ui.renderGraph();
  }
  function switchProject(projectId) {
    state.projectId = projectId || null;
    clearProjectDerivedState();
    store.resetProject(state.projectId);
    router.update({
      projectId: state.projectId,
      table: null,
      leftVersion: null,
      rightVersion: null,
      focus: null
    });
    return loadProjectData();
  }
  function syncDetailDraftHint(message, dirty) {
    const hint = $("detailDraftHint");
    if (!hint) return;
    hint.innerHTML = `<strong>提示：</strong>${escapeHtml(message || "字段备注与表级元数据会集中提交保存，不逐行自动写入。")}`;
    $("detailSaveBtn").disabled = !dirty;
  }
  function collectDetailDraftPayload() {
    if (!state.selectedTableName || !state.detailDraft) return null;
    const draft = state.detailDraft;
    return {
      tables: [{
        table_name: state.selectedTableName,
        display_name: draft.table.display_name || "",
        owner: draft.table.owner || "",
        update_frequency: draft.table.update_frequency || "",
        retention: draft.table.retention || "",
        note: draft.table.note || ""
      }],
      columns: Object.entries(draft.columns).map(([columnName, value]) => ({
        table_name: state.selectedTableName,
        column_name: columnName,
        display_name: value.display_name || "",
        note: value.note || "",
        business_tag: value.business_tag || ""
      })),
      revision_meta: metadataRevisionPayload()
    };
  }
  function bindDetailEditors(fields) {
    const draft = {
      table: {
        display_name: $("detailDisplayName")?.value || "",
        owner: $("detailOwner")?.value || "",
        update_frequency: $("detailFrequency")?.value || "",
        retention: $("detailRetention")?.value || "",
        note: $("detailNote")?.value || ""
      },
      columns: Object.fromEntries((fields || []).map(field => [field.name, {
        display_name: field.display_name || "",
        note: field.note || "",
        business_tag: field.business_tag || ""
      }]))
    };
    state.detailDraft = draft;
    const markDirty = () => syncDetailDraftHint("已修改表级或字段级元数据；点击“保存元数据”后统一提交。", true);
    [["detailDisplayName","display_name"],["detailOwner","owner"],["detailFrequency","update_frequency"],["detailRetention","retention"],["detailNote","note"]].forEach(([id,key]) => {
      const el = $(id);
      if (!el) return;
      el.oninput = () => { draft.table[key] = el.value.trim(); markDirty(); };
    });
    document.querySelectorAll("[data-detail-col]").forEach(el => {
      el.oninput = () => {
        const column = el.dataset.detailCol;
        const key = el.dataset.detailKey;
        if (!draft.columns[column]) draft.columns[column] = {display_name:"", note:"", business_tag:""};
        draft.columns[column][key] = el.value.trim();
        markDirty();
      };
    });
    syncDetailDraftHint("字段备注与表级元数据会集中提交保存，不逐行自动写入。", false);
  }
  async function saveDetailMetadata() {
    const payload = collectDetailDraftPayload();
    if (!payload) return ui.showToast("请先打开一张表详情");
    state.metadataPreviewContext = {
      defaultSource: "detail_editor",
      reason: `更新表 ${state.selectedTableName} 的表级/字段级元数据`
    };
    const preview = await previewDictionaryBulk(payload);
    const ok = await openMetadataPreview(preview, `保存前变更预览 · ${state.selectedTableName}`);
    if (!ok) return;
    payload.revision_meta = metadataRevisionPayload();
    const result = await saveDictionaryBulk(payload);
    syncDetailDraftHint("保存成功，已回写表级与字段级元数据。", false);
    await loadProjectData();
    await loadTableDetail(state.selectedTableName);
    ui.showToast(`元数据已保存：表 ${result.saved_tables}，字段 ${result.saved_columns}`);
  }
  async function loadTableDetail(name) {
    if (!name || !state.projectId || state.mode !== "live") return null;
    const projectId = state.projectId;
    const generation = store.getState().requestGeneration;
    setSelectedTable(name);
    const detail = await apis.detail.get(projectId, name);
    if (projectId !== state.projectId || name !== state.selectedTableName || generation !== store.getState().requestGeneration) return null;
    state.selectedTableDetail = detail;
    renderTableDetail(detail);
    await loadDetailDiff(name);
    return detail;
  }
  function renderTableDetail(payload) {
    const table = payload && payload.table;
    if (!table) return;
    const layer = String(table.layer || "OTHER").toUpperCase();
    $("detailEyebrow").textContent = `Table detail · ${layer}`;
    $("detailTitle").textContent = table.name || "未命名表";
    $("detailSubtitle").textContent = table.display_name || table.description || `${layer} 层真实表详情`;
    $("detailLayer").innerHTML = `<span class="tag" style="--tag:${layer === "ODS" ? "var(--ods)" : layer === "DWD" ? "var(--dwd)" : layer === "DWS" ? "var(--dws)" : layer === "ADS" ? "var(--ads)" : "#55718c"}">${escapeHtml(layer)}</span>`;
    $("detailGrain").textContent = (table.grain || []).length ? table.grain.join(" · ") : "未识别";
    $("detailParseSource").textContent = table.parse_source || "unknown";
    $("detailTimeFields").textContent = (table.time_fields || []).join(", ") || "—";
    $("detailUpstreamCount").textContent = `${table.upstream_count || 0} 张表`;
    $("detailDownstreamCount").textContent = `${table.downstream_count || 0} 张表`;
    if ($("detailDisplayName")) $("detailDisplayName").value = table.display_name || "";
    if ($("detailOwner")) $("detailOwner").value = table.owner || "";
    if ($("detailFrequency")) $("detailFrequency").value = table.update_frequency || "";
    if ($("detailRetention")) $("detailRetention").value = table.retention || "";
    if ($("detailNote")) $("detailNote").value = table.note || "";
    const fields = payload.fields || [];
    $("detailFieldRows").innerHTML = fields.length ? fields.map(field => `<tr>
      <td><div class="table-name">${escapeHtml(field.name)}</div><div class="table-desc">${escapeHtml((field.source_tables || []).join(", ") || "—")}</div><input class="mini-input" data-detail-col="${escapeHtml(field.name)}" data-detail-key="display_name" value="${escapeHtml(field.display_name || "")}" placeholder="中文名 / 展示名"></td>
      <td class="mono">${escapeHtml(field.type || "—")}</td>
      <td><span class="tag" style="--tag:${tagColor(field.kind)}">${escapeHtml(field.kind || field.role || "field")}</span>${field.semantic_type ? `<div class="table-desc">${escapeHtml(field.semantic_type)}</div>` : ""}<input class="mini-input" data-detail-col="${escapeHtml(field.name)}" data-detail-key="business_tag" value="${escapeHtml(field.business_tag || "")}" placeholder="业务标签"></td>
      <td class="mono">${escapeHtml((field.source_fields || []).join(", ") || "—")}</td>
      <td class="mono">${escapeHtml(field.expression || "直接映射 / 无表达式")}</td>
      <td><textarea class="inline-note" data-detail-col="${escapeHtml(field.name)}" data-detail-key="note" placeholder="业务含义 / 口径备注">${escapeHtml(field.note || "")}</textarea></td>
    </tr>`).join("") : `<tr><td colspan="6"><div class="empty-shell"><strong>暂无字段信息</strong>该表可能是推断表或未提供完整 DDL。</div></td></tr>`;
    const evidence = payload.evidence || [];
    const metrics = payload.metrics || [];
    const operations = payload.operations || [];
    const importMeta = payload.import_meta || {};
    $("detailEvidence").innerHTML = evidence.length ? evidence.map(item => `<div class="evidence-block"><label>${escapeHtml(item.type === "ddl" ? "DDL" : "ETL")}</label><p class="mono">${escapeHtml(item.file || "—")}${item.line ? `<br>第 ${escapeHtml(item.line)} 行` : ""}</p>${item.summary ? `<p>${escapeHtml(item.summary)}</p>` : ""}${item.sources && item.sources.length ? `<p class="table-desc">来源：${escapeHtml(item.sources.join(", "))}</p>` : ""}${item.file_available ? `<p class="table-desc"><a href="${escapeHtml(resolveApiHref(item.content_url))}" target="_blank" rel="noreferrer">查看原文</a> · <a href="${escapeHtml(resolveApiHref(item.export_url))}">导出文件</a></p>` : `<p class="table-desc">历史版本未保存原始文件</p>`}</div>`).join("") : '<div class="empty-shell"><strong>暂无证据</strong>没有找到与该表关联的 DDL / ETL 证据。</div>';
    const risks = payload.risks || [];
    $("detailRisks").innerHTML = risks.length ? risks.map(item => `<div class="risk" style="padding-bottom:0"><div class="risk-icon">!</div><div><strong>${escapeHtml(item.code || item.severity || "风险")}</strong><p>${escapeHtml(item.message || "—")}</p>${item.file ? `<p class="table-desc mono">${escapeHtml(item.file)}</p>` : ""}</div></div>`).join("") : '<div class="empty-shell"><strong>暂无风险</strong>当前未在该表关联脚本中发现质量提示。</div>';
    $("detailRelations").innerHTML = `<div class="evidence-block"><label>上游表</label><p>${escapeHtml((table.upstream_tables || []).join("，") || "无")}</p></div><div class="evidence-block"><label>下游表</label><p>${escapeHtml((table.downstream_tables || []).join("，") || "无")}</p></div><div class="evidence-block"><label>分区 / 分布</label><p>${escapeHtml(table.partition_type ? `${table.partition_type}(${(table.partition_columns || []).join(", ")})` : "未识别")}</p>${table.distribute_columns && table.distribute_columns.length ? `<p class="table-desc mono">DISTRIBUTE BY ${escapeHtml(table.distribute_columns.join(", "))}</p>` : ""}</div><div class="evidence-block"><label>指标数量</label><p>${escapeHtml(table.metric_count || 0)} 个</p></div>`;
    $("detailMetrics").innerHTML = metrics.length ? metrics.slice(0, 8).map(item => `<div class="evidence-block"><label>${escapeHtml(item.name || "未命名指标")}</label><p class="mono">${escapeHtml(item.formula || "—")}</p><p class="table-desc">粒度：${escapeHtml((item.grain || []).join("，") || "未识别")}</p>${item.filter ? `<p class="table-desc">过滤：${escapeHtml(item.filter)}</p>` : ""}</div>`).join("") : '<div class="empty-shell"><strong>暂无指标</strong>该表当前没有识别到聚合指标。</div>';
    $("detailOperations").innerHTML = operations.length ? operations.slice(0, 6).map(item => `<div class="evidence-block"><label>${escapeHtml(item.type || "operation")}</label><p class="mono">${escapeHtml(item.file || "—")}${item.line ? `<br>第 ${escapeHtml(item.line)} 行` : ""}</p><p class="table-desc">来源：${escapeHtml((item.sources || []).join("，") || "无")}</p>${item.group_by && item.group_by.length ? `<p class="table-desc">GROUP BY：${escapeHtml(item.group_by.join("，"))}</p>` : ""}${item.where ? `<p class="table-desc">WHERE：${escapeHtml(item.where)}</p>` : ""}</div>`).join("") : '<div class="empty-shell"><strong>暂无操作摘要</strong>没有找到与该表直接关联的写入操作。</div>';
    const metadataRevision = payload.metadata_revision || null;
    $("detailVersion").innerHTML = `<div class="evidence-block"><label>分析版本</label><p>${escapeHtml(importMeta.version || payload.version || "—")}</p></div><div class="evidence-block"><label>导入状态</label><p>${escapeHtml(importMeta.status || "completed")}</p></div><div class="evidence-block"><label>导入文件</label><p class="mono">${escapeHtml(importMeta.filename || "—")}</p>${importMeta.id ? `<p class="table-desc"><a href="${escapeHtml(apiRoot + `/imports/${importMeta.id}/files/export`)}">导出本版本全部导入文件</a></p>` : ""}</div><div class="evidence-block"><label>分析时间</label><p>${escapeHtml(importMeta.created_at || "—")}</p></div><div class="evidence-block"><label>元数据修订</label><p>${metadataRevision ? `R${escapeHtml(metadataRevision.revision)}` : "尚未形成修订"}</p>${metadataRevision ? `<p class="table-desc">基于分析版本 ${escapeHtml(metadataRevision.import_version || "—")}</p><p class="table-desc">来源：${escapeHtml(metadataRevision.source || "—")} · 操作人：${escapeHtml(metadataRevision.operator || "—")}</p>${metadataRevision.reason ? `<p class="table-desc">原因：${escapeHtml(metadataRevision.reason)}</p>` : ""}` : ""}</div>`;
    bindDetailEditors(fields);
    renderDetailDiff();
  }
  function renderCompareResult(result) {
    state.compareResult = result;
    const summary = result.summary || {};
    const count = (...values) => {
      for (const value of values) {
        if (Array.isArray(value)) return value.length;
        if (Number.isFinite(Number(value))) return Number(value);
      }
      return 0;
    };
    const tables = result.tables || result.table_changes || {};
    const metrics = result.metrics || result.metric_changes || {};
    const lineage = result.lineage || result.lineage_changes || {};
    const addedTotal = count(summary.tables_added, tables.added) + count(summary.metrics_added, metrics.added) + count(summary.lineage_added, lineage.added);
    const changedTotal = count(summary.tables_changed, tables.modified) + count(summary.metrics_changed, metrics.modified);
    const removedTotal = count(summary.tables_removed, tables.removed) + count(summary.metrics_removed, metrics.removed) + count(summary.lineage_removed, lineage.removed);
    const cards = $("compareSummaryCards");
    if (cards) {
      cards.innerHTML = [
        ["新增", addedTotal || count(summary.added), "var(--success)", "#e6f5ee"],
        ["修改", changedTotal || count(summary.changed, summary.modified), "var(--warning)", "#fff0df"],
        ["删除", removedTotal || count(summary.removed), "var(--danger)", "#ffe9eb"],
        ["受影响 ADS", count(summary.impacted_ads, summary.affected_ads, result.affected_ads), "var(--accent)", "#e8f1fb"]
      ].map(item => `<div class="card stat" style="--tint:${item[3]}"><div class="label">${item[0]}</div><div class="value" style="color:${item[2]}">${item[1]}</div></div>`).join("");
    }
    const changes = [];
    (tables.changed || []).filter(item =>
      !item?.change || item.change === "modified" || item.change === "changed"
    ).slice(0, 8).forEach(item => {
      const counts = item.columns || {};
      const table = item.table || item.name || item.object || "未命名表";
      const columnList = Array.isArray(counts) ? counts : null;
      const addedColumns = columnList ? columnList.filter(column => column.change === "added").length : count(counts.added);
      const removedColumns = columnList ? columnList.filter(column => column.change === "removed").length : count(counts.removed);
      const changedColumns = columnList ? columnList.filter(column => column.change === "modified" || column.change === "changed").length : count(counts.changed, counts.modified);
      changes.push(`<div class="change"><span class="change-type modify">~ 表结构</span><div><strong class="mono">${escapeHtml(table)}</strong><div class="table-desc">新增字段 ${escapeHtml(addedColumns)}，删除字段 ${escapeHtml(removedColumns)}，属性变化 ${escapeHtml(changedColumns)}</div></div><div class="head-actions"><button class="btn" data-compare-open-detail="${escapeHtml(table)}">表详情</button><button class="btn" data-compare-impact="${escapeHtml(table)}">分析影响</button></div></div>`);
    });
    (metrics.changed || metrics.modified || []).slice(0, 6).forEach(item => {
      const value = typeof item === "string" ? { metric: item } : item;
      const metric = value.metric || value.name || value.object || "未命名指标";
      const table = value.table || value.table_name || "";
      changes.push(`<div class="change"><span class="change-type modify">~ 指标口径</span><div><strong class="mono">${escapeHtml(metric)}</strong><div class="table-desc">${escapeHtml(Object.keys(value.changes || value.diff || {}).join("、") || "表达式变化")}</div></div><div class="head-actions">${table ? `<button class="btn" data-compare-open-detail="${escapeHtml(table)}">定位表</button>` : ""}<button class="btn" data-compare-impact="${escapeHtml(table ? `${table}.${metric}` : metric)}">分析影响</button></div></div>`);
    });
    (tables.added || []).slice(0, 4).forEach(item => {
      const value = typeof item === "string" ? { name: item } : item;
      changes.push(`<div class="change"><span class="change-type add">＋ 新增表</span><div><strong class="mono">${escapeHtml(value.name || value.table)}</strong><div class="table-desc">${escapeHtml(value.layer || "OTHER")} · ${escapeHtml(value.column_count || 0)} 字段</div></div><button class="btn" data-compare-open-detail="${escapeHtml(value.name || value.table)}">查看详情</button></div>`);
    });
    (tables.removed || []).slice(0, 4).forEach(item => {
      const value = typeof item === "string" ? { name: item } : item;
      changes.push(`<div class="change"><span class="change-type delete">− 删除表</span><div><strong class="mono">${escapeHtml(value.name || value.table)}</strong><div class="table-desc">${escapeHtml(value.layer || "OTHER")} · 原字段 ${escapeHtml(value.column_count || 0)}</div></div><button class="btn" data-compare-impact="${escapeHtml(value.name || value.table)}">分析影响</button></div>`);
    });
    const metadataCompare = state.metadataCompareResult;
    const metadataChanges = metadataCompare ? [
      ...(metadataCompare.tables || []).slice(0, 4).map(item => `<div class="change"><span class="change-type modify">~ 元数据表</span><div><strong class="mono">${escapeHtml(item.table_name)}</strong><div class="table-desc">${escapeHtml(item.change_type || "属性变化")}</div></div></div>`),
      ...(metadataCompare.columns || []).slice(0, 6).map(item => `<div class="change"><span class="change-type modify">~ 元数据字段</span><div><strong class="mono">${escapeHtml(item.table_name)}.${escapeHtml(item.column_name)}</strong><div class="table-desc">${escapeHtml(item.change_type || "属性变化")}</div></div></div>`)
    ] : [];
    const allChanges = [...changes, ...metadataChanges];
    $("compareChangeList").innerHTML = `<div class="section-head"><h2>结构化差异</h2><span class="subtle" style="font-size:11px">表 / 指标 / 血缘 / 元数据</span></div>${allChanges.length ? allChanges.join("") : '<div class="load-state"><strong>未发现显著差异</strong>两次分析的结构、血缘和元数据基本一致。</div>'}`;
    if (state.selectedTableName) renderDetailDiff();
  }
  Object.assign(ctx, { allAssets, bindDetailEditors, clearProjectDerivedState, closeMetadataPreview, collectDetailDraftPayload, csvLine, downloadText, fetchImportMetaByVersion, loadDetailDiff, loadTableDetail, openMetadataPreview, renderCompareMeta, renderCompareResult, renderDetailDiff, renderMetadataPreview, renderTableDetail, saveDetailMetadata, selectedAssets, setSelectedTable, switchProject, syncDetailDraftHint });
}
