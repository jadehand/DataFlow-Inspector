(function () {
  "use strict";

  const params = new URLSearchParams(location.search);
  const suppliedRoot = params.get("api");
  // 默认后端：开发模式下 15173 的前端自动指向 18080 的后端
  const defaultApi = location.port === "15173" ? "http://127.0.0.1:18080/api"
    : location.protocol === "file:" ? "http://127.0.0.1:18080/api"
    : location.origin + "/api";
  const apiRoot = (suppliedRoot || defaultApi).replace(/\/+$/, "");
  const state = {
    mode: "connecting",
    projectId: null,
    projects: [],
    versions: [],
    wizardStep: 1,
    preflight: null,
    importResult: null,
    tablePreview: null,
    selectedRelationIndex: null,
    selectedTableName: null,
    selectedTableDetail: null,
    detailDraft: null,
    compareResult: null,
    metadataCompareResult: null,
    selectedVersionMeta: {},
    selectedAssets: [],
    metadataRevisions: [],
    metadataPreviewResolver: null,
    metadataPreviewContext: null,
    impactSeed: null
  };
  const $ = id => document.getElementById(id);
  const ui = window.DFI_UI;
  const tableStrategyLabels = {
    check: "先预览并检测冲突",
    confirm_precise: "确认精确导入",
    merge_inferred: "确认推断关系并导入",
    accept_orphan: "作为孤立表导入",
    replace: "覆盖已有表定义",
    keep: "保留已有版本",
    merge: "合并字段与血缘"
  };

  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
  }
  function unwrap(value, keys) {
    if (Array.isArray(value)) return value;
    for (const key of keys) if (value && Array.isArray(value[key])) return value[key];
    return [];
  }
  async function request(path, options) {
    const response = await fetch(apiRoot + path, Object.assign({headers:{Accept:"application/json"}}, options || {}));
    const text = await response.text();
    let body = null;
    if (text) {
      try { body = JSON.parse(text); } catch (_) { body = text; }
    }
    if (!response.ok || (body && body.error)) {
      const detail = body && (body.detail || body.error || body.message);
      throw new Error(typeof detail === "string" ? detail : "HTTP " + response.status);
    }
    return body;
  }
  async function saveDictionaryBulk(payload) {
    if (!state.projectId) throw new Error("请先选择项目");
    return request(`/projects/${encodeURIComponent(state.projectId)}/dictionary/bulk`, {
      method:"PUT",
      headers:{"Content-Type":"application/json",Accept:"application/json"},
      body:JSON.stringify(payload)
    });
  }
  async function previewDictionaryBulk(payload) {
    if (!state.projectId) throw new Error("请先选择项目");
    return request(`/projects/${encodeURIComponent(state.projectId)}/dictionary/bulk/preview`, {
      method:"POST",
      headers:{"Content-Type":"application/json",Accept:"application/json"},
      body:JSON.stringify(payload)
    });
  }
  async function fetchMetadataRevisions() {
    if (!state.projectId) return [];
    const payload = await request(`/projects/${encodeURIComponent(state.projectId)}/metadata/revisions`);
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
    const payload = await request(`/projects/${encodeURIComponent(state.projectId)}/metadata/compare?left=${encodeURIComponent(left)}&right=${encodeURIComponent(right)}`);
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
    return [
      escapeHtml(m.display_name || m.business_name || m.name || m.field_name || "未命名指标"),
      escapeHtml(m.field_name || m.code || m.name || "—"),
      escapeHtml(m.formula || m.expression || m.sql_expression || "—"),
      escapeHtml(Array.isArray(m.time_grain || m.grain) ? (m.time_grain || m.grain).join(" + ") : (m.time_grain || m.grain || "待识别")),
      m.confirmed === false || m.status === "inferred" ? "待确认" : "已确认"
    ];
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
      d: escapeHtml(n.description || n.desc || "数据资产")
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
  async function fetchImportMetaByVersion(versionValue) {
    const version = state.versions.find(item => String(item.version ?? item.id) === String(versionValue));
    if (!version || !version.id) return null;
    if (state.selectedVersionMeta[version.id]) return state.selectedVersionMeta[version.id];
    const detail = await request(`/imports/${encodeURIComponent(version.id)}`);
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
    if (state.versions.length < 2) {
      $("detailDiff").innerHTML = '<div class="empty-shell"><strong>暂无差异摘要</strong>当前项目不足两个分析版本。</div>';
      return;
    }
    const left = state.versions[1]?.id;
    const right = state.versions[0]?.id;
    if (!left || !right) return renderDetailDiff();
    try {
      const query = new URLSearchParams({left: String(left), right: String(right)});
      const result = await request(`/projects/${encodeURIComponent(state.projectId)}/tables/${encodeURIComponent(name)}/compare?${query}`);
      renderDetailDiff(result);
    } catch (_) {
      renderDetailDiff();
    }
  }
  function setSelectedTable(name) {
    state.selectedTableName = name || null;
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
    setSelectedTable(name);
    const detail = await request(`/projects/${encodeURIComponent(state.projectId)}/tables/${encodeURIComponent(name)}/detail`);
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
    $("detailEvidence").innerHTML = evidence.length ? evidence.map(item => `<div class="evidence-block"><label>${escapeHtml(item.type === "ddl" ? "DDL" : "ETL")}</label><p class="mono">${escapeHtml(item.file || "—")}${item.line ? `<br>第 ${escapeHtml(item.line)} 行` : ""}</p>${item.summary ? `<p>${escapeHtml(item.summary)}</p>` : ""}${item.sources && item.sources.length ? `<p class="table-desc">来源：${escapeHtml(item.sources.join(", "))}</p>` : ""}</div>`).join("") : '<div class="empty-shell"><strong>暂无证据</strong>没有找到与该表关联的 DDL / ETL 证据。</div>';
    const risks = payload.risks || [];
    $("detailRisks").innerHTML = risks.length ? risks.map(item => `<div class="risk" style="padding-bottom:0"><div class="risk-icon">!</div><div><strong>${escapeHtml(item.code || item.severity || "风险")}</strong><p>${escapeHtml(item.message || "—")}</p>${item.file ? `<p class="table-desc mono">${escapeHtml(item.file)}</p>` : ""}</div></div>`).join("") : '<div class="empty-shell"><strong>暂无风险</strong>当前未在该表关联脚本中发现质量提示。</div>';
    $("detailRelations").innerHTML = `<div class="evidence-block"><label>上游表</label><p>${escapeHtml((table.upstream_tables || []).join("，") || "无")}</p></div><div class="evidence-block"><label>下游表</label><p>${escapeHtml((table.downstream_tables || []).join("，") || "无")}</p></div><div class="evidence-block"><label>分区 / 分布</label><p>${escapeHtml(table.partition_type ? `${table.partition_type}(${(table.partition_columns || []).join(", ")})` : "未识别")}</p>${table.distribute_columns && table.distribute_columns.length ? `<p class="table-desc mono">DISTRIBUTE BY ${escapeHtml(table.distribute_columns.join(", "))}</p>` : ""}</div><div class="evidence-block"><label>指标数量</label><p>${escapeHtml(table.metric_count || 0)} 个</p></div>`;
    $("detailMetrics").innerHTML = metrics.length ? metrics.slice(0, 8).map(item => `<div class="evidence-block"><label>${escapeHtml(item.name || "未命名指标")}</label><p class="mono">${escapeHtml(item.formula || "—")}</p><p class="table-desc">粒度：${escapeHtml((item.grain || []).join("，") || "未识别")}</p>${item.filter ? `<p class="table-desc">过滤：${escapeHtml(item.filter)}</p>` : ""}</div>`).join("") : '<div class="empty-shell"><strong>暂无指标</strong>该表当前没有识别到聚合指标。</div>';
    $("detailOperations").innerHTML = operations.length ? operations.slice(0, 6).map(item => `<div class="evidence-block"><label>${escapeHtml(item.type || "operation")}</label><p class="mono">${escapeHtml(item.file || "—")}${item.line ? `<br>第 ${escapeHtml(item.line)} 行` : ""}</p><p class="table-desc">来源：${escapeHtml((item.sources || []).join("，") || "无")}</p>${item.group_by && item.group_by.length ? `<p class="table-desc">GROUP BY：${escapeHtml(item.group_by.join("，"))}</p>` : ""}${item.where ? `<p class="table-desc">WHERE：${escapeHtml(item.where)}</p>` : ""}</div>`).join("") : '<div class="empty-shell"><strong>暂无操作摘要</strong>没有找到与该表直接关联的写入操作。</div>';
    const metadataRevision = payload.metadata_revision || null;
    $("detailVersion").innerHTML = `<div class="evidence-block"><label>分析版本</label><p>${escapeHtml(importMeta.version || payload.version || "—")}</p></div><div class="evidence-block"><label>导入状态</label><p>${escapeHtml(importMeta.status || "completed")}</p></div><div class="evidence-block"><label>导入文件</label><p class="mono">${escapeHtml(importMeta.filename || "—")}</p></div><div class="evidence-block"><label>分析时间</label><p>${escapeHtml(importMeta.created_at || "—")}</p></div><div class="evidence-block"><label>元数据修订</label><p>${metadataRevision ? `R${escapeHtml(metadataRevision.revision)}` : "尚未形成修订"}</p>${metadataRevision ? `<p class="table-desc">基于分析版本 ${escapeHtml(metadataRevision.import_version || "—")}</p><p class="table-desc">来源：${escapeHtml(metadataRevision.source || "—")} · 操作人：${escapeHtml(metadataRevision.operator || "—")}</p>${metadataRevision.reason ? `<p class="table-desc">原因：${escapeHtml(metadataRevision.reason)}</p>` : ""}` : ""}</div>`;
    bindDetailEditors(fields);
    renderDetailDiff();
  }
  function renderCompareResult(result) {
    state.compareResult = result;
    const summary = result.summary || {};
    const cards = $("compareSummaryCards");
    if (cards) {
      cards.innerHTML = [
        ["新增", summary.tables_added + summary.metrics_added + summary.lineage_added, "var(--success)", "#e6f5ee"],
        ["修改", summary.tables_changed + summary.metrics_changed, "var(--warning)", "#fff0df"],
        ["删除", summary.tables_removed + summary.metrics_removed + summary.lineage_removed, "var(--danger)", "#ffe9eb"],
        ["受影响 ADS", summary.impacted_ads || 0, "var(--accent)", "#e8f1fb"]
      ].map(item => `<div class="card stat" style="--tint:${item[3]}"><div class="label">${item[0]}</div><div class="value" style="color:${item[2]}">${item[1]}</div></div>`).join("");
    }
    const changes = [];
    (result.tables?.changed || []).slice(0, 8).forEach(item => {
      const counts = item.columns || {};
      changes.push(`<div class="change"><span class="change-type modify">~ 表结构</span><div><strong class="mono">${escapeHtml(item.table)}</strong><div class="table-desc">新增字段 ${escapeHtml(counts.added?.length || 0)}，删除字段 ${escapeHtml(counts.removed?.length || 0)}，属性变化 ${escapeHtml(counts.changed?.length || 0)}</div></div><div class="head-actions"><button class="btn" data-compare-open-detail="${escapeHtml(item.table)}">表详情</button><button class="btn" data-compare-impact="${escapeHtml(item.table)}">分析影响</button></div></div>`);
    });
    (result.metrics?.changed || []).slice(0, 6).forEach(item => {
      changes.push(`<div class="change"><span class="change-type modify">~ 指标口径</span><div><strong class="mono">${escapeHtml(item.metric)}</strong><div class="table-desc">${escapeHtml(Object.keys(item.changes || {}).join("、") || "表达式变化")}</div></div><div class="head-actions"><button class="btn" data-compare-open-detail="${escapeHtml(item.table)}">定位表</button><button class="btn" data-compare-impact="${escapeHtml(item.table)}.${escapeHtml(item.name)}">分析影响</button></div></div>`);
    });
    (result.tables?.added || []).slice(0, 4).forEach(item => {
      changes.push(`<div class="change"><span class="change-type add">＋ 新增表</span><div><strong class="mono">${escapeHtml(item.name)}</strong><div class="table-desc">${escapeHtml(item.layer || "OTHER")} · ${escapeHtml(item.column_count || 0)} 字段</div></div><button class="btn" data-compare-open-detail="${escapeHtml(item.name)}">查看详情</button></div>`);
    });
    (result.tables?.removed || []).slice(0, 4).forEach(item => {
      changes.push(`<div class="change"><span class="change-type delete">− 删除表</span><div><strong class="mono">${escapeHtml(item.name)}</strong><div class="table-desc">${escapeHtml(item.layer || "OTHER")} · 原字段 ${escapeHtml(item.column_count || 0)}</div></div><button class="btn" data-compare-impact="${escapeHtml(item.name)}">分析影响</button></div>`);
    });
    const metadataCompare = state.metadataCompareResult;
    const metadataChanges = metadataCompare ? [
      ...(metadataCompare.tables || []).slice(0, 4).map(item => `<div class="change"><span class="change-type modify">~ 元数据表</span><div><strong class="mono">${escapeHtml(item.table_name)}</strong><div class="table-desc">${escapeHtml(item.change_type)} · ${escapeHtml(Object.keys(item.changes || {}).join("、") || "属性变化")}</div></div><div class="head-actions"><button class="btn" data-compare-open-detail="${escapeHtml(item.table_name)}">表详情</button><button class="btn" data-compare-impact="${escapeHtml(item.table_name)}" data-compare-scope="metadata_revision">分析影响</button></div></div>`),
      ...(metadataCompare.columns || []).slice(0, 6).map(item => `<div class="change"><span class="change-type modify">~ 元数据字段</span><div><strong class="mono">${escapeHtml(item.table_name)}.${escapeHtml(item.column_name)}</strong><div class="table-desc">${escapeHtml(item.change_type)} · ${escapeHtml(Object.keys(item.changes || {}).join("、") || "属性变化")}</div></div><div class="head-actions"><button class="btn" data-compare-open-detail="${escapeHtml(item.table_name)}">定位表</button><button class="btn" data-compare-impact="${escapeHtml(item.table_name)}.${escapeHtml(item.column_name)}" data-compare-scope="metadata_revision">分析影响</button></div></div>`)
    ] : [];
    $("compareChangeList").innerHTML = `<div class="section-head"><h2>结构化差异</h2><span class="subtle" style="font-size:11px">表 / 指标 / 血缘 / 元数据</span></div>${[...changes, ...metadataChanges].length ? [...changes, ...metadataChanges].join("") : '<div class="load-state"><strong>未发现显著差异</strong>两次分析的结构、血缘和元数据基本一致。</div>'}`;
    if (state.selectedTableName) renderDetailDiff();
  }
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
      const payload = await request("/projects");
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
      state.projectId = state.projectId || state.projects[0].id;
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
    const id = encodeURIComponent(state.projectId);
    const results = await Promise.allSettled([
      request(`/projects/${id}/tables`),
      request(`/projects/${id}/lineage`),
      request(`/projects/${id}/workflows`),
      request(`/projects/${id}/metrics`),
      request(`/projects/${id}/quality-findings`),
      request(`/projects/${id}/imports`),
      request(`/projects/${id}/metadata/revisions`)
    ]);
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
    state.versions = results[5].status === "fulfilled" ? unwrap(results[5].value, ["imports","versions","items","data"]) : [];
    state.metadataRevisions = results[6].status === "fulfilled" ? unwrap(results[6].value, ["revisions","items","data"]) : [];
    updateLiveSummaries(tableList, jobs, findings, metricList);
    updateVersions();
    renderCompareMeta(null, null);
    if (state.selectedTableName) {
      try { await loadTableDetail(state.selectedTableName); } catch (_) {}
    }
    if (failures.length) ui.showToast(`真实项目已加载，${failures.length} 类数据接口暂不可用`);
    else ui.showToast("真实项目数据已加载");
  }
  function updateLiveSummaries(tableList, jobs, findings, metricList) {
    const values = document.querySelectorAll("#page-overview .stat .value");
    if (values[0]) values[0].textContent = String(tableList.length);
    if (values[1]) values[1].textContent = String(tableList.reduce((total, table) =>
      total + (table.column_count ?? (table.columns || table.fields || []).length), 0));
    if (values[2]) values[2].textContent = String(metricList.length);
    if (values[3]) values[3].textContent = String(findings.length);
    $("sideStats").textContent = `${tableList.length} 张表 · ${metricList.length} 个指标 · ${findings.length} 项风险`;
    const project = state.projects.find(item => String(item.id) === String(state.projectId));
    const projectTitle = document.querySelector("#page-overview h1");
    if (projectTitle && project) projectTitle.textContent = project.name || project.project_name || "数据加工项目";
    const workflowStats = document.querySelectorAll("#page-workflow .grid.cols-3 .eyebrow");
    if (workflowStats[0]) workflowStats[0].textContent = `${jobs.length} jobs`;
    if (workflowStats[1]) workflowStats[1].textContent = `${jobs.filter(j => j.confirmed === false || j.status === "inferred").length} inferred`;
    const riskList = document.querySelector("#page-overview .risk-list");
    if (riskList && findings.length) {
      riskList.innerHTML = findings.slice(0, 3).map(f => `<div class="risk ${f.severity === "high" ? "high" : ""}"><div class="risk-icon">!</div><div><strong>${escapeHtml(f.message || f.title || f.code || "质量风险")}</strong><p>${escapeHtml(f.file || f.object || "来自真实项目分析")}</p></div></div>`).join("");
    }
  }
  function updateVersions() {
    if (!state.versions.length) return;
    const options = state.versions.map(v => `<option value="${escapeHtml(v.version ?? v.id)}">${escapeHtml(v.version || v.note || v.created_at || v.id)}</option>`).join("");
    $("compareLeft").innerHTML = options;
    $("compareRight").innerHTML = options;
    if (state.versions.length > 1) $("compareLeft").selectedIndex = 1;
    const leftOption = $("compareLeft").value;
    const rightOption = $("compareRight").value;
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
    const result = await request("/projects", {method:"POST",headers:{"Content-Type":"application/json",Accept:"application/json"},body:JSON.stringify({name})});
    const id = result.id || (result.project && result.project.id);
    if (!id) throw new Error("后端未返回新项目 ID");
    state.projectId = id;
    await loadProjects();
    return id;
  }
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
    const result = await request(`/projects/${encodeURIComponent(state.projectId)}/tables/preview`, {
      method:"POST", headers:{"Content-Type":"application/json",Accept:"application/json"},
      body:JSON.stringify({
        ddl,
        etl_sql: $("tableEtlInput").value.trim()
      })
    });
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
    const result = await request(`/projects/${encodeURIComponent(state.projectId)}/tables/import`, {
      method:"POST", headers:{"Content-Type":"application/json",Accept:"application/json"},
      body:JSON.stringify({
        ddl,
        etl_sql: $("tableEtlInput").value.trim(),
        conflict_strategy: strategy,
        confirmed_relation_index: confirmedRelationIndex
      })
    });
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
      const result = await request("/imports/preflight", {
        method:"POST", headers:{"Content-Type":"application/zip",Accept:"application/json"}, body:file
      });
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
      const note = encodeURIComponent($("importVersionNote").value.trim());
      const result = await request(`/projects/${encodeURIComponent(state.projectId)}/imports?filename=${encodeURIComponent(file.name)}&note=${note}`, {
        method:"POST", headers:{"Content-Type":"application/zip",Accept:"application/json"}, body:file
      });
      state.importResult = result;
      progress.textContent = "上传成功，分析批次：" + (result.id || result.import_id || "已创建");
      $("importConfirm").hidden = true;
      $("importComplete").hidden = false;
      $("importSummary").innerHTML = analysisSummary(result).map(item => `<div class="summary-item"><strong>${item[1]}</strong><span>${item[0]}</span></div>`).join("");
      $("wizardNext").hidden = true;
      $("wizardBack").hidden = true;
      $("wizardCancel").textContent = "关闭";
      await loadProjectData();
    } catch (error) { showImportError(error); throw error; }
  }
  async function runImpact() {
    if (state.mode !== "live") {
      $("impactResult").classList.add("show");
      return ui.showToast("演示影响结果已展示（未调用后端）");
    }
    const button = $("runImpact"); button.disabled = true; button.textContent = "正在沿真实血缘分析…";
    try {
      const result = await request(`/projects/${encodeURIComponent(state.projectId)}/impact-analysis`, {
        method:"POST", headers:{"Content-Type":"application/json",Accept:"application/json"},
        body:JSON.stringify(Object.assign({
          object:$("changeObject").value,
          change_type:$("changeType").value,
          before:$("beforeValue").value,
          after:$("afterValue").value
        }, state.impactSeed || {}))
      });
      $("impactResult").classList.add("show");
      renderImpactResult(result);
      ui.showToast("真实影响分析完成：" + (result.affected_count ?? result.total_affected ?? "结果已返回"));
    } catch (error) { ui.showToast("影响分析失败：" + error.message); }
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
    const [label, score] = riskMap[result.risk] || ["中风险", 50];
    $("impactScore").textContent = String(score);
    $("impactRiskLabel").textContent = label;
    const total = (result.transitive_impacts || []).length;
    $("impactHeadline").textContent = `变更将传递到 ${total} 个下游对象`;
    $("impactSummaryText").textContent = `${(result.scripts || []).length} 个脚本、${(result.metrics || []).length} 个指标、${(result.ads_tables || []).length} 张 ADS 需要关注。`;
    const objectName = $("changeObject").value || result.change?.object || "变更对象";
    const paths = result.paths || [];
    $("impactTree").innerHTML = [`<div class="tree-row" style="--depth:0"><span class="tag" style="--tag:var(--accent)">ROOT</span><strong class="mono">${escapeHtml(objectName)}</strong></div>`].concat(paths.slice(0, 12).map((item, index) => `<div class="tree-row" style="--depth:${Math.min(index + 1, 4)}"><span class="tree-line"></span><span class="tag" style="--tag:${String(item.target || "").toLowerCase().includes("ads") ? "var(--ads)" : "var(--dws)"}">${escapeHtml(String(item.target || "").split(".")[0] || "TABLE")}</span><span class="mono">${escapeHtml(item.target || "—")}</span></div>`)).join("");
    $("impactRecommendations").innerHTML = (result.recommendations || []).map((item, index) => `<div class="flow-row"><div class="flow-code">${index + 1}</div><div><strong>${escapeHtml(item)}</strong><div class="table-desc">${index === 0 ? "建议先修改上游定义，再顺序回归下游。" : "来自真实影响分析返回。"}</div></div></div>`).join("");
    renderImpactEvidence(result);
  }
  async function runComparison() {
    if (state.mode !== "live") return ui.showToast("当前为演示版本比较，未调用后端");
    try {
      const query = new URLSearchParams({left:$("compareLeft").value,right:$("compareRight").value});
      const result = await request(`/projects/${encodeURIComponent(state.projectId)}/compare?${query}`);
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
      ui.navigate("detail");
      return ui.showToast("演示模式下仅展示静态详情样式");
    }
    try {
      await loadTableDetail(name);
      ui.navigate("detail");
    } catch (error) {
      ui.showToast("表详情加载失败：" + error.message);
    }
  }
  async function exportServerDictionary() {
    if (state.mode !== "live" || !state.projectId) return ui.showToast("请先连接真实后端并选择项目");
    try {
      const response = await fetch(`${apiRoot}/projects/${encodeURIComponent(state.projectId)}/dictionary/export`, {headers:{Accept:"text/csv"}});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const blob = await response.blob();
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
      const answer = await request(`/projects/${encodeURIComponent(state.projectId)}/assistant/query`, {
        method:"POST",headers:{"Content-Type":"application/json",Accept:"application/json"},body:JSON.stringify({question})
      });
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

  $("apiEndpoint").textContent = apiRoot;
  $("retryConnection").onclick = loadProjects;
  $("demoModeBtn").onclick = () => { setMode("demo"); ui.restoreDemo(); $("projectSelect").innerHTML = '<option>Token 请求流量（内置演示）</option>'; ui.showToast("已显式切换到演示模式"); };
  $("refreshBtn").onclick = () => state.mode === "live" ? loadProjectData() : loadProjects();
  $("projectSelect").onchange = event => { state.projectId = event.target.value; loadProjectData(); };
  $("tableImportBtn").onclick = openTableDrawer;
  $("assetTableImportBtn").onclick = openTableDrawer;
  $("exportAssetDictionaryBtn").onclick = () => exportServerDictionary();
  $("bulkEditBtn").onclick = runBulkDraftEdit;
  $("bulkImpactBtn").onclick = runBulkImpactSeed;
  $("bulkExportBtn").onclick = exportSelectedAssets;
  $("importBtn").onclick = openWizard;
  $("drawer").querySelector(".drawer-close").onclick = closeWizard;
  $("wizardCancel").onclick = closeWizard;
  $("wizardBack").onclick = () => setWizardStep(Math.max(1, state.wizardStep - 1));
  $("wizardNext").onclick = nextWizardStep;
  document.querySelectorAll('input[name="projectMode"]').forEach(input => input.onchange = updateProjectMode);
  document.querySelectorAll(".package-tab").forEach(button => button.onclick = () => renderPackageTree(button.dataset.package));
  $("importFile").onchange = () => {
    const file = $("importFile").files[0];
    state.preflight = null;
    $("fileMeta").classList.toggle("show", Boolean(file));
    if (file) { $("fileName").textContent = file.name; $("fileSize").textContent = formatBytes(file.size); }
    $("preflightArea").innerHTML = '<div class="load-state"><strong>尚未执行预检</strong>点击“检查项目包”获取后端真实检查结果。</div>';
  };
  $("replaceFile").onclick = () => $("importFile").click();
  $("downloadBlankTemplate").onclick = () => {
    if (state.mode === "live") location.href = apiRoot + "/templates/blank";
    else downloadGuideFallback();
  };
  $("downloadDemoPackage").onclick = () => {
    if (state.mode === "live") location.href = apiRoot + "/templates/demo";
    else {
      const link = document.createElement("a");
      link.href = "../../examples/token-traffic-demo.zip";
      link.download = "token-traffic-demo.zip";
      link.click();
    }
  };
  $("gotoAssets").onclick = () => { closeWizard(); ui.navigate("assets"); };
  $("gotoLineage").onclick = () => { closeWizard(); ui.navigate("lineage"); };
  $("tableDrawerClose").onclick = closeTableDrawer;
  $("tablePreviewBtn").onclick = async () => {
    try { await runTablePreview(); } catch (error) { tableDrawerStatus("预览失败：" + error.message, true); }
  };
  $("tableImportRunBtn").onclick = async () => {
    try { await runTableImport(); } catch (error) { tableDrawerStatus("导入失败：" + error.message, true); }
  };
  $("tablePreviewArea").onclick = event => {
    const target = event.target.closest("[data-table-strategy]");
    if (!target) return;
    const strategy = target.dataset.tableStrategy;
    if (strategy) $("tableConflictStrategy").value = strategy;
    if (target.dataset.relationIndex != null) state.selectedRelationIndex = Number(target.dataset.relationIndex);
  };
  $("tableDrawer").onclick = event => { if (event.target === $("tableDrawer")) closeTableDrawer(); };
  $("drawer").addEventListener("keydown", event => {
    if (event.key === "Escape") closeWizard();
    if (event.key === "Tab") {
      const focusable = [...$("drawer").querySelectorAll('button:not([hidden]):not([disabled]),input:not([hidden]),select:not([hidden])')].filter(el => el.offsetParent !== null);
      if (!focusable.length) return;
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });
  $("tableDrawer").addEventListener("keydown", event => {
    if (event.key === "Escape") closeTableDrawer();
  });
  $("metadataPreviewClose").onclick = () => closeMetadataPreview(false);
  $("metadataPreviewCancel").onclick = () => closeMetadataPreview(false);
  $("metadataPreviewConfirm").onclick = () => closeMetadataPreview(true);
  $("metadataPreviewDrawer").onclick = event => { if (event.target === $("metadataPreviewDrawer")) closeMetadataPreview(false); };
  renderPackageTree(params.get("package") === "recommended" ? "recommended" : "minimum");
  $("runImpact").onclick = runImpact;
  $("runCompare").onclick = runComparison;
  $("detailSaveBtn").onclick = saveDetailMetadata;
  $("detailLineageBtn").onclick = () => {
    if (!state.selectedTableName) return ui.showToast("请先打开一张表详情");
    ui.navigate("lineage");
    const focused = typeof ui.focusNode === "function" && ui.focusNode(state.selectedTableName);
    if (!focused) {
      setTimeout(() => {
        const done = typeof ui.focusNode === "function" && ui.focusNode(state.selectedTableName);
        if (!done && typeof ui.focusHint === "function") {
          ui.focusHint(`未在当前血缘图中定位到 ${state.selectedTableName}`);
        } else if (done && typeof ui.focusHint === "function") {
          ui.focusHint(`已聚焦 ${state.selectedTableName}`);
        }
      }, 80);
    } else if (typeof ui.focusHint === "function") {
      ui.focusHint(`已聚焦 ${state.selectedTableName}`);
    }
  };
    $("detailImpactBtn").onclick = () => {
      if (!state.selectedTableName) return ui.showToast("请先打开一张表详情");
      prepareImpactContext({
        object: state.selectedTableName,
      changeType: "加工逻辑变化",
      before: state.selectedTableDetail?.table?.ddl_file || "当前定义",
        after: "待调整",
        context: `已从表详情带入 ${state.selectedTableName}。`
      });
      state.impactSeed = null;
      ui.navigate("impact");
    };
  $("detailExportBtn").onclick = exportDetailJson;
  $("exportCompareBtn").onclick = exportCompareResult;
  $("compareLeft").onchange = updateCompareMeta;
  $("compareRight").onchange = updateCompareMeta;
  ui.onAssetSelect = openDetailForTable;
  ui.onNodeSelect = openDetailForTable;
  ui.onAssetSelectionChange = rows => {
    state.selectedAssets = rows || [];
    $("bulkImpactBtn").disabled = !rows.length;
    $("bulkExportBtn").disabled = !rows.length;
    $("bulkEditBtn").disabled = !rows.length;
  };
  $("sendChat").onclick = () => { const input=$("chatInput"), value=input.value.trim(); if(value){input.value="";ask(value);} };
  $("chatInput").onkeydown = event => { if(event.key === "Enter") $("sendChat").click(); };
  document.querySelectorAll(".suggestion").forEach(item => item.onclick = () => ask(item.textContent.trim()));
  $("compareChangeList").onclick = event => {
    const detailTarget = event.target.closest("[data-compare-open-detail]");
    if (detailTarget) {
      openDetailForTable(detailTarget.dataset.compareOpenDetail);
      return;
    }
    const impactTarget = event.target.closest("[data-compare-impact]");
    if (impactTarget) {
      const scope = impactTarget.dataset.compareScope || "project";
      prepareImpactContext({
        object: impactTarget.dataset.compareImpact,
        changeType: "加工逻辑变化",
        before: "上一版本",
        after: "当前版本",
        context: `已从版本比较带入 ${impactTarget.dataset.compareImpact}。`
      });
      if (scope === "metadata_revision" && state.metadataCompareResult) {
        prepareImpactSeed({
          compare_scope: "metadata_revision",
          left_revision: Number(state.metadataCompareResult.left_revision?.revision),
          right_revision: Number(state.metadataCompareResult.right_revision?.revision)
        });
      } else {
        prepareImpactSeed({
          compare_scope: "project",
          left_version: Number($("compareLeft").value),
          right_version: Number($("compareRight").value)
        });
      }
      ui.navigate("impact");
    }
  };
  loadProjects();
  const wizardDeepLink = Number(params.get("wizard"));
  if (wizardDeepLink >= 1 && wizardDeepLink <= 4) {
    setTimeout(() => {
      openWizard();
      setWizardStep(wizardDeepLink);
    }, 250);
  }
}());
