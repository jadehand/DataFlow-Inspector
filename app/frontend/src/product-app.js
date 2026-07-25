(function () {
  "use strict";

  const params = new URLSearchParams(location.search);
  const suppliedRoot = params.get("api");
  const apiRoot = (suppliedRoot || (location.protocol === "file:" ? "http://127.0.0.1:18080/api" : location.origin + "/api")).replace(/\/+$/, "");
  const state = { mode: "connecting", projectId: null, projects: [], versions: [], latestImport: null, wizardStep: 1, preflight: null, importResult: null, activeDiagnostic: null, diagnosticTrigger: null, tables: [], tableEdges: [], columnEdges: [], jobs: [], jobEdges: [], metrics: [] };
  const $ = id => document.getElementById(id);
  const ui = window.DFI_UI;

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
      const detail = body && (body.message || body.detail || body.error);
      const error = new Error(typeof detail === "string" ? detail : "HTTP " + response.status);
      error.status = response.status;
      error.payload = body;
      throw error;
    }
    return body;
  }
  function setMode(mode, message) {
    state.mode = mode;
    const pill = $("connectionPill"), banner = $("modeBanner");
    pill.className = "connection-pill" + (mode === "live" ? " live" : mode === "connecting" ? " loading" : "");
    pill.textContent = mode === "live" ? "真实数据" : mode === "error" ? "连接失败" : "连接中";
    $("apiEndpoint").textContent = apiRoot;
    banner.classList.toggle("show", mode === "error");
    $("modeBannerTitle").textContent = "后端连接失败";
    $("modeBannerText").textContent = message || "无法读取分析服务，请确认本机服务已启动后重试。";
    $("retryConnection").textContent = "重新连接";
    const sideDot = $("sideDot");
    sideDot.style.background = mode === "live" ? "var(--success)" : mode === "error" ? "var(--danger)" : "var(--accent)";
    sideDot.style.boxShadow = "none";
    $("sideVersion").textContent = mode === "live" ? "真实分析服务已连接"
      : mode === "error" ? "分析服务连接失败" : "正在连接分析服务…";
  }
  function showWorkspaceState(kind, values) {
    const content = document.querySelector(".content");
    content.classList.remove("state-welcome", "state-project-empty", "state-loading", "state-error");
    document.querySelectorAll(".nav button").forEach(button => { button.disabled = Boolean(kind); });
    const assistantButton = document.querySelector('.top-actions [data-goto="assistant"]');
    if (assistantButton) assistantButton.disabled = Boolean(kind);
    if (!kind) return;
    content.classList.add("state-" + kind);
    const copy = Object.assign({
      kicker: "开始建立数据地图",
      title: "还没有分析项目",
      message: "导入脱敏后的 DDL、加工 SQL 和作业清单，生成表、字段、血缘、指标与风险视图。",
      create: "＋ 创建第一个项目",
      retry: false,
      foot: "你的资料只会发送到当前配置的内网分析服务。"
    }, values || {});
    $("emptyKicker").textContent = copy.kicker;
    $("emptyTitle").textContent = copy.title;
    $("emptyMessage").textContent = copy.message;
    $("emptyCreateBtn").textContent = copy.create;
    $("emptyCreateBtn").hidden = copy.create === false;
    $("emptyRetryBtn").hidden = !copy.retry;
    $("emptyFoot").textContent = copy.foot;
  }
  function currentProject() {
    return state.projects.find(item => String(item.id) === String(state.projectId));
  }
  function projectStatus(project) {
    // The imports endpoint is authoritative after an upload. A newly-created
    // project's cached list item can still say import_count=0 until /projects is
    // fetched again, which previously hid a successfully loaded analysis.
    if (state.latestImport) {
      const status = String(state.latestImport.status || "completed").toLowerCase();
      if (["processing", "queued", "running"].includes(status)) return "processing";
      if (["failed", "error"].includes(status)) return "failed";
      return "completed";
    }
    if (state.versions.length) return "completed";
    if (!project || !Number(project.import_count || 0)) return "empty";
    const status = String(project.latest_import_status || project.status || "completed").toLowerCase();
    if (["processing", "queued", "running"].includes(status)) return "processing";
    if (["failed", "error"].includes(status)) return "failed";
    return "completed";
  }
  function normalizeTable(t, tableEdges, timeUsage, findings) {
    const columns = t.columns || t.fields || [];
    const name = t.qualified_name || t.qualifiedName || t.full_name || t.name;
    const upstreamNames = t.upstreams || [...new Set(tableEdges.filter(e => e.target === name).map(e => e.source))];
    const downstreamNames = t.downstreams || [...new Set(tableEdges.filter(e => e.source === name).map(e => e.target))];
    const times = [...new Set(timeUsage.filter(item => item.target === name).flatMap(item => item.fields || []))];
    const metrics = state.metrics.filter(metric => metric.table === name);
    const grains = [...new Set(metrics.flatMap(metric => metric.grain || []))];
    const evidence = [
      ...tableEdges.filter(edge => edge.source === name || edge.target === name),
      ...(t.write_evidence || []).map(item => ({
        ...item, source:(item.sources || []).join(", ") || "常量/表达式", target:name
      }))
    ];
    const risk = findings.some(item => !item.file || evidence.some(edge => edge.file === item.file));
    return {
      name,
      desc: t.description || t.comment || "",
      layer: String(t.layer || "OTHER").toUpperCase(),
      grain: Array.isArray(t.grain) ? (t.grain.join(" + ") || "待识别") : (t.grain || t.data_grain || (grains.length ? grains.join(" + ") : "待识别")),
      time: t.time_field || t.core_time_field || t.timeField || t.primary_time_column || (times.length ? times.join("、") : "—"),
      fields: t.column_count ?? columns.length,
      relation: upstreamNames.length + " / " + downstreamNames.length,
      risk: Boolean(t.risk || t.has_risk || t.status === "warning" || risk),
      columns,
      upstream: upstreamNames,
      downstream: downstreamNames,
      evidence,
      ddlFile: t.ddl_file || t.ddlFile,
      inferred: Boolean(t.inferred)
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
    const inLane = index % 3;
    return {
      id: n.qualified_name || n.qualifiedName || n.name || n.id || n.table_id,
      x: 8 + lane * 220,
      y: 45 + inLane * 104,
      n: n.qualified_name || n.qualifiedName || n.name || n.label || n.id,
      l: layer === "RDS" ? "SOURCE" : layer,
      d: n.description || n.desc || "数据资产"
    };
  }
  function setProjectOptions() {
    const select = $("projectSelect");
    select.innerHTML = state.projects.map(p => {
      const suffix = Number(p.import_count || 0) ? "" : " · 待导入";
      return `<option value="${escapeHtml(p.id)}">${escapeHtml(p.name || p.project_name || p.id)}${suffix}</option>`;
    }).join("");
    if (state.projectId != null) select.value = String(state.projectId);
    select.disabled = false;
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
    showWorkspaceState("loading", {
      kicker: "正在连接内网服务", title: "正在读取项目", message: "确认分析服务与项目元数据状态。",
      create: false, retry: false, foot: apiRoot
    });
    $("projectMenuBtn").disabled = true;
    try {
      const payload = await request("/projects");
      state.projects = unwrap(payload, ["projects","items","data"]);
      if (!state.projects.length) {
        $("projectSelect").innerHTML = '<option value="">尚无项目，请导入项目包</option>';
        $("projectSelect").disabled = true;
        state.projectId = null;
        state.versions = [];
        state.latestImport = null;
        syncWizardProjects();
        setMode("live");
        $("importBtn").disabled = false;
        $("importBtn").textContent = "＋ 创建项目";
        $("sideStats").textContent = "尚无项目";
        showWorkspaceState("welcome");
        return;
      }
      if (!state.projects.some(project => String(project.id) === String(state.projectId))) state.projectId = state.projects[0].id;
      setProjectOptions();
      setMode("live");
      $("importBtn").disabled = false;
      $("projectMenuBtn").disabled = false;
      $("importBtn").textContent = "＋ 导入新版本";
      await loadProjectData();
    } catch (error) {
      setMode("error", "无法连接后端：" + error.message + "。请检查本机服务是否已启动。");
      $("projectSelect").innerHTML = '<option value="">后端不可用</option>';
      $("projectSelect").disabled = true;
      state.projectId = null;
      state.versions = [];
      state.latestImport = null;
      $("importBtn").textContent = "＋ 创建项目";
      $("importBtn").disabled = true;
      showWorkspaceState("error", {
        kicker: "服务不可用", title: "无法连接分析服务", message: "请检查本机服务是否启动、地址是否正确，然后重新连接。",
        create: false, retry: true, foot: "当前服务地址：" + apiRoot
      });
    }
  }
  async function loadProjectData() {
    if (!state.projectId || state.mode !== "live") return;
    showWorkspaceState("loading", {
      kicker: "正在加载真实项目", title: "正在读取分析结果", message: "同步表、字段、血缘、指标、风险和导入历史。",
      create: false, retry: false, foot: "当前页面只展示已导入项目的真实分析结果。"
    });
    const id = encodeURIComponent(state.projectId);
    const results = await Promise.allSettled([
      request(`/projects/${id}/tables`),
      request(`/projects/${id}/lineage`),
      request(`/projects/${id}/workflows`),
      request(`/projects/${id}/metrics`),
      request(`/projects/${id}/quality-findings`),
      request(`/projects/${id}/imports`)
    ]);
    const failures = results.slice(0, 5).filter(r => r.status === "rejected");
    state.versions = results[5].status === "fulfilled" ? unwrap(results[5].value, ["imports","versions","items","data"]) : [];
    state.latestImport = state.versions[0] || null;
    const project = currentProject();
    if (project && state.versions.length) {
      // Keep the selector and subsequent in-memory status checks consistent
      // without triggering another loadProjects -> loadProjectData cycle.
      project.import_count = state.versions.length;
      project.latest_import_status = state.latestImport?.status || project.latest_import_status || "completed";
      setProjectOptions();
    }
    const status = projectStatus(project);
    updateProjectManagement();
    if (!state.versions.length || status === "empty") {
      $("sideStats").textContent = "项目已创建 · 尚未导入";
      showWorkspaceState("project-empty", {
        kicker: "项目已创建", title: "导入第一份项目资料",
        message: "当前项目还没有分析版本。上传 ZIP 后才会生成总览、血缘和指标。",
        create: "导入项目资料", retry: false, foot: "当前项目：" + (project?.name || project?.project_name || state.projectId)
      });
      return;
    }
    if (status === "processing") {
      $("sideStats").textContent = "最新版本正在分析";
      showWorkspaceState("project-empty", {
        kicker: "分析任务运行中", title: "正在生成项目地图",
        message: "系统正在解析 DDL、SQL、字段血缘与指标。可以刷新状态查看最新进度。",
        create: false, retry: true, foot: "分析版本：v" + (state.latestImport.version || "—")
      });
      return;
    }
    if (status === "failed") {
      $("sideStats").textContent = "最新分析失败";
      showWorkspaceState("project-empty", {
        kicker: "分析需要处理", title: "最新版本分析失败",
        message: state.latestImport ? normalizeDiagnostic(state.latestImport).message : "打开项目管理查看失败记录，可以重新分析或导入修正后的资料。",
        create: "导入修正版", retry: false, foot: "失败版本：v" + (state.latestImport?.version || "—")
      });
      return;
    }
    const tableList = results[0].status === "fulfilled" ? unwrap(results[0].value, ["tables","items","data"]) : [];
    const lineagePayload = results[1].status === "fulfilled" ? results[1].value : null;
    let rawNodes = unwrap(lineagePayload, ["nodes","tables","items"]);
    const rawEdges = unwrap(lineagePayload, ["edges","lineage","data"]);
    if (!rawNodes.length && rawEdges.length) {
      const tableMap = new Map(tableList.map(t => [t.name, t]));
      const names = [...new Set(rawEdges.flatMap(e => [e.source, e.target]))];
      rawNodes = names.map(name => Object.assign({id:name,name}, tableMap.get(name) || {}));
    }
    state.tableEdges = rawEdges;
    const metricPayload = results[3].status === "fulfilled" ? results[3].value : null;
    const metricList = unwrap(metricPayload, ["metrics","items","data"]);
    const timeUsage = unwrap(metricPayload, ["time_usage"]);
    state.metrics = metricList;
    const findingPayload = results[4].status === "fulfilled" ? results[4].value : null;
    const findings = unwrap(findingPayload, ["findings","risks","items","data"]);
    state.tables = tableList.map(table => normalizeTable(table, rawEdges, timeUsage, findings));
    ui.setTables(state.tables);
    ui.renderAssets();
    ui.renderAssetDetail();
    ui.setNodes(rawNodes.map(normalizeNode));
    ui.setEdges(rawEdges);
    ui.renderGraph();
    ui.setMetrics(metricList.map(normalizeMetric));
    ui.renderMetrics();
    const workflowPayload = results[2].status === "fulfilled" ? results[2].value : null;
    const jobs = unwrap(workflowPayload, ["jobs","items","data"]);
    const jobEdges = unwrap(workflowPayload, ["edges","lineage"]);
    state.jobs = jobs;
    state.jobEdges = jobEdges;
    ui.renderWorkflow(jobs, jobEdges);
    updateLiveSummaries(tableList, jobs, findings, metricList);
    updateVersions();
    showWorkspaceState(null);
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
    const deltas = document.querySelectorAll("#page-overview .stat .delta");
    if (deltas[0]) deltas[0].textContent = `${new Set(tableList.map(table => table.layer).filter(Boolean)).size} 个加工层级`;
    if (deltas[1]) deltas[1].textContent = "来自最新完成版本";
    if (deltas[2]) deltas[2].textContent = "静态解析识别";
    if (deltas[3]) deltas[3].textContent = findings.length ? "需要人工确认" : "当前未发现";
    $("sideStats").textContent = `${tableList.length} 张表 · ${metricList.length} 个指标 · ${findings.length} 项风险`;
    const project = currentProject();
    const projectTitle = document.querySelector("#page-overview h1");
    if (projectTitle && project) projectTitle.textContent = project.name || project.project_name || "数据加工项目";
    const subtitle = document.querySelector("#page-overview .page-head .subtle");
    if (subtitle) subtitle.textContent = `真实项目分析结果 · 最新版本 v${state.latestImport?.version || "—"} · ${formatDate(state.latestImport?.completed_at || state.latestImport?.created_at)}`;
    const workflowStats = document.querySelectorAll("#page-workflow .grid.cols-3 .eyebrow");
    if (workflowStats[0]) workflowStats[0].textContent = `${jobs.length} jobs`;
    if (workflowStats[1]) workflowStats[1].textContent = `${jobs.filter(j => j.confirmed === false || j.status === "inferred").length} inferred`;
    const riskList = document.querySelector("#page-overview .risk-list");
    if (riskList) riskList.innerHTML = findings.length
      ? findings.slice(0, 3).map(f => `<div class="risk ${f.severity === "high" ? "high" : ""}"><div class="risk-icon">!</div><div><strong>${escapeHtml(f.message || f.title || f.code || "质量风险")}</strong><p>${escapeHtml(f.file || f.object || "来自真实项目分析")}</p></div></div>`).join("")
      : '<div class="load-state"><strong>当前未发现质量风险</strong>结果来自最新完成的真实分析版本。</div>';
    const flowList = document.querySelector("#page-overview .flow-list");
    if (flowList) flowList.innerHTML = jobs.length
      ? jobs.slice(0, 4).map((job, index) => `<div class="flow-row"><div class="flow-code">${String(index + 1).padStart(2, "0")}</div><div><strong>${escapeHtml(job.name || job.job_name || job.id || "未命名作业")}</strong><div class="flow-meta"><span>${escapeHtml(job.type || job.job_type || "SQL")}</span><span>${escapeHtml(job.schedule || job.cron || "顺序待确认")}</span></div></div><span class="health ${job.confirmed === false ? "warn" : "ok"}">${job.confirmed === false ? "待确认" : "已识别"}</span></div>`).join("")
      : '<div class="load-state"><strong>未识别到作业清单</strong>可在项目包中补充 metadata/jobs.csv。</div>';
    const counts = tableList.reduce((map, table) => {
      const layer = String(table.layer || "SOURCE").toUpperCase();
      map[layer] = (map[layer] || 0) + 1;
      return map;
    }, {});
    document.querySelectorAll(".pipe-node").forEach(node => {
      const layer = node.dataset.layer;
      const small = node.querySelector("small");
      if (!small) return;
      if (layer === "SOURCE") small.textContent = String((counts.SOURCE || 0) + (counts.RDS || 0));
      else if (layer === "DWD") small.textContent = String((counts.DWD || 0) + (counts.DIM || 0));
      else small.textContent = String(counts[layer] || 0);
    });
    $("messages").innerHTML = '<div class="msg ai"><div class="avatar">✦</div><div class="bubble">已连接当前真实项目。可以询问字段来源、指标口径、时间关系或变更影响；回答会基于已导入资料。</div></div>';
  }
  function updateVersions() {
    if (!state.versions.length) {
      $("compareLeft").innerHTML = '<option value="">尚无分析版本</option>';
      $("compareRight").innerHTML = '<option value="">尚无分析版本</option>';
      return;
    }
    const options = state.versions.map(v => `<option value="${escapeHtml(v.version ?? v.id)}">${escapeHtml(v.version || v.note || v.created_at || v.id)}</option>`).join("");
    $("compareLeft").innerHTML = options;
    $("compareRight").innerHTML = options;
    if (state.versions.length > 1) $("compareLeft").selectedIndex = 1;
  }
  function statusLabel(status) {
    const value = String(status || "unknown").toLowerCase();
    if (["completed", "success", "ready"].includes(value)) return ["completed", "分析完成"];
    if (["processing", "queued", "running"].includes(value)) return ["processing", "分析中"];
    if (["failed", "error"].includes(value)) return ["failed", "分析失败"];
    return ["", "状态未知"];
  }
  function formatDate(value) {
    if (!value) return "时间未知";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString("zh-CN", {hour12:false});
  }
  function maybeJson(value) {
    if (typeof value !== "string" || !/^\s*\{/.test(value)) return value;
    try { return JSON.parse(value); } catch (_) { return value; }
  }
  function friendlyFailureMessage(value) {
    const text = String(value || "").trim();
    if (!text) return "分析过程中发生错误，未生成本次分析结果。";
    if (/analysis failed|unexpected analysis failure/i.test(text)) return "SQL/DDL 分析过程中发生内部错误，未生成本次分析结果。";
    return text;
  }
  function stageLabel(value) {
    const key = String(value || "").toLowerCase();
    if (!key) return "SQL / DDL 分析";
    if (key.includes("preflight") || key.includes("validate")) return "项目包预检";
    if (key.includes("extract") || key.includes("unzip")) return "项目包解压";
    if (key.includes("persist") || key.includes("save")) return "结果保存";
    if (key.includes("parse") || key.includes("analy")) return "SQL / DDL 分析";
    if (key.includes("import") || key.includes("upload")) return "项目资料导入";
    return String(value);
  }
  function normalizeDiagnostic(value) {
    const outer = value instanceof Error ? (value.payload || {}) : (value || {});
    const legacyValue = maybeJson(value instanceof Error ? value.message : outer.error);
    let detail = maybeJson(
      outer.error_detail || outer.error_details || outer.diagnostic || outer.failure ||
      (outer.detail && typeof outer.detail === "object" ? outer.detail : null) ||
      (outer.error && typeof outer.error === "object" ? outer.error : null)
    );
    if (detail && typeof detail === "object" && (detail.error_detail || detail.diagnostic)) {
      detail = maybeJson(detail.error_detail || detail.diagnostic);
    }
    const source = detail && typeof detail === "object" ? detail : {};
    const rawMessage = source.safe_message || source.message ||
      (typeof outer.message === "string" ? outer.message : "") ||
      (typeof outer.detail === "string" ? outer.detail : "") ||
      (typeof legacyValue === "string" ? legacyValue : "") ||
      (value instanceof Error ? value.message : "");
    const suggestionValue = source.suggestion || source.suggestions || source.advice || source.recommendation;
    const suggestion = Array.isArray(suggestionValue) ? suggestionValue.join("；") : suggestionValue;
    const code = source.code || source.error_code || outer.code ||
      (/analysis failed|unexpected analysis failure/i.test(rawMessage) ? "analysis_failed" : "unknown_error");
    const diagnostic = {
      stage: stageLabel(source.stage || source.phase || outer.stage),
      code: String(code || "unknown_error"),
      id: String(source.error_id || source.trace_id || source.request_id || outer.error_id || "未生成"),
      file: String(source.file || source.filename || source.source_file || source.path || outer.filename || outer.file || "未定位到具体文件"),
      message: friendlyFailureMessage(rawMessage),
      suggestion: String(suggestion || (Object.keys(source).length
        ? "根据错误原因检查对应文件，修正后重新导入；如仍失败，请复制诊断信息交给维护人员。"
        : "当前记录来自旧版错误格式，未包含具体原因。请查看本机 app.log，或升级后重新分析以生成完整诊断。")),
      logPath: String(source.log_path || source.log_location || source.log_file || outer.log_path || "%LOCALAPPDATA%\\DataFlow Inspector\\logs\\app.log")
    };
    diagnostic.copyText = [
      "DataFlow Inspector 导入诊断",
      `失败阶段：${diagnostic.stage}`,
      `错误码：${diagnostic.code}`,
      `错误编号：${diagnostic.id}`,
      `关联文件：${diagnostic.file}`,
      `错误原因：${diagnostic.message}`,
      `建议处理：${diagnostic.suggestion}`,
      `日志位置：${diagnostic.logPath}`
    ].join("\n");
    return diagnostic;
  }
  function openDiagnostic(value, trigger) {
    const diagnostic = normalizeDiagnostic(value);
    state.activeDiagnostic = diagnostic;
    state.diagnosticTrigger = trigger || document.activeElement;
    $("diagnosticMessage").textContent = diagnostic.message;
    $("diagnosticStage").textContent = diagnostic.stage;
    $("diagnosticCode").textContent = diagnostic.code;
    $("diagnosticId").textContent = diagnostic.id;
    $("diagnosticFile").textContent = diagnostic.file;
    $("diagnosticSuggestion").textContent = diagnostic.suggestion;
    $("diagnosticCopyText").textContent = diagnostic.copyText;
    $("diagnosticLogPath").textContent = diagnostic.logPath;
    $("diagnosticDialog").classList.add("open");
    setTimeout(() => $("diagnosticClose").focus(), 0);
  }
  function closeDiagnostic() {
    $("diagnosticDialog").classList.remove("open");
    const trigger = state.diagnosticTrigger;
    state.diagnosticTrigger = null;
    if (trigger && trigger.isConnected) trigger.focus();
  }
  async function copyDiagnostic() {
    if (!state.activeDiagnostic) return;
    const text = state.activeDiagnostic.copyText;
    try {
      if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error("clipboard unavailable");
      await navigator.clipboard.writeText(text);
    } catch (_) {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      textarea.remove();
    }
    ui.showToast("诊断信息已复制，可直接发给维护人员");
  }
  function updateProjectManagement() {
    const project = currentProject();
    if (!project) return;
    $("managedProjectName").textContent = project.name || project.project_name || `项目 ${project.id}`;
    $("managedVersion").textContent = state.versions.length ? `${state.versions.length} 个版本` : "尚无版本";
    const [statusClass, label] = statusLabel(state.latestImport?.status || (state.versions.length ? "completed" : ""));
    $("managedStatus").className = "analysis-state " + statusClass;
    $("managedStatus").textContent = state.versions.length ? label : "尚未分析";
    $("reanalyzeBtn").disabled = !state.latestImport || ["processing", "queued", "running"].includes(String(state.latestImport.status).toLowerCase());
    $("historyList").innerHTML = state.versions.length ? state.versions.map((item, index) => {
      const [css, text] = statusLabel(item.status);
      const failed = css === "failed";
      const diagnostic = failed ? normalizeDiagnostic(item) : null;
      const error = diagnostic
        ? `<small style="color:var(--danger)">${escapeHtml(diagnostic.message)}</small><button class="history-error-action" data-diagnostic-index="${index}">查看错误详情 →</button>`
        : "";
      return `<article class="history-item"><div><strong>v${escapeHtml(item.version || "—")} · ${escapeHtml(item.filename || "项目包")}</strong><small>${escapeHtml(formatDate(item.completed_at || item.created_at))} · 尝试 ${escapeHtml(item.attempts || 1)} 次</small>${error}</div><span class="analysis-state ${css}">${text}</span></article>`;
    }).join("") : '<div class="empty-inline">还没有导入记录。点击“导入新版本”开始分析。</div>';
  }
  async function refreshHistory() {
    if (!state.projectId || state.mode !== "live") return;
    $("historyList").innerHTML = '<div class="load-state">正在读取导入历史…</div>';
    try {
      const payload = await request(`/projects/${encodeURIComponent(state.projectId)}/imports`);
      state.versions = unwrap(payload, ["imports","versions","items","data"]);
      state.latestImport = state.versions[0] || null;
      updateProjectManagement();
      updateVersions();
    } catch (error) {
      $("historyList").innerHTML = `<div class="load-state error"><strong>历史读取失败</strong>${escapeHtml(error.message)}</div>`;
    }
  }
  function openProjectManagement() {
    if (!state.projectId || state.mode !== "live") return;
    updateProjectManagement();
    $("projectDrawer").classList.add("open");
    refreshHistory();
    setTimeout(() => $("projectDrawerClose").focus(), 0);
  }
  function closeProjectManagement() {
    $("projectDrawer").classList.remove("open");
    $("projectMenuBtn").focus();
  }
  async function reanalyzeLatest() {
    if (!state.latestImport) return ui.showToast("当前项目还没有可重新分析的版本");
    const button = $("reanalyzeBtn");
    button.disabled = true;
    button.textContent = "正在重新分析…";
    try {
      const result = await request(`/imports/${encodeURIComponent(state.latestImport.id)}/reanalyze`, {method:"POST"});
      state.latestImport = Object.assign({}, state.latestImport, result);
      ui.showToast(result.status === "completed" ? "重新分析完成" : "重新分析任务已启动");
      await loadProjects();
      closeProjectManagement();
    } catch (error) {
      ui.showToast("重新分析失败：" + error.message);
      await refreshHistory();
    } finally {
      button.disabled = false;
      button.textContent = "重新分析最新版本";
    }
  }
  async function deleteCurrentProject() {
    const project = currentProject();
    if (!project) return;
    const name = project.name || project.project_name || project.id;
    if (!window.confirm(`确定删除项目“${name}”吗？所有导入版本和分析结果都将永久删除。`)) return;
    const button = $("deleteProjectBtn");
    button.disabled = true;
    try {
      await request(`/projects/${encodeURIComponent(state.projectId)}`, {method:"DELETE"});
      closeProjectManagement();
      state.projectId = null;
      ui.showToast("项目已删除");
      await loadProjects();
    } catch (error) {
      ui.showToast("删除失败：" + error.message);
    } finally {
      button.disabled = false;
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
    if (state.mode !== "live") throw new Error("分析服务未连接，请重新连接后再创建项目");
    const result = await request("/projects", {method:"POST",headers:{"Content-Type":"application/json",Accept:"application/json"},body:JSON.stringify({name})});
    const id = result.id || (result.project && result.project.id);
    if (!id) throw new Error("后端未返回新项目 ID");
    state.projectId = id;
    await loadProjects();
    return id;
  }
  function showImportError(error) {
    const box = $("importProgress");
    const diagnostic = normalizeDiagnostic(error);
    state.activeDiagnostic = diagnostic;
    box.classList.add("show");
    box.style.background = "#fff0f2";
    box.style.color = "var(--danger)";
    box.innerHTML = `<strong>导入分析失败</strong><span>${escapeHtml(diagnostic.message)}</span><button class="btn" id="showImportDiagnostic" type="button">查看错误详情</button>`;
    $("showImportDiagnostic").onclick = event => openDiagnostic(error, event.currentTarget);
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
    if (state.mode !== "live") throw new Error("分析服务未连接，无法执行项目包预检");
    const file = $("importFile").files[0];
    if (!file || !/\.zip$/i.test(file.name)) throw new Error("请选择有效的 ZIP 项目包");
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
    if (state.mode !== "live") throw new Error("分析服务未连接，无法上传文件");
    if (!state.preflight) throw new Error("请先完成真实预检");
    const file = $("importFile").files[0];
    if (!file) throw new Error("请选择 ZIP 项目包");
    const projectId = await ensureProject();
    const progress = $("importProgress");
    progress.classList.add("show"); progress.style.background = ""; progress.style.color = ""; progress.textContent = "正在上传并启动解析…";
    try {
      const note = encodeURIComponent($("importVersionNote").value.trim());
      const result = await request(`/projects/${encodeURIComponent(projectId)}/imports?filename=${encodeURIComponent(file.name)}&note=${note}`, {
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
    if (state.mode !== "live") return ui.showToast("分析服务未连接，无法执行影响分析");
    const button = $("runImpact"); button.disabled = true; button.textContent = "正在沿真实血缘分析…";
    try {
      const result = await request(`/projects/${encodeURIComponent(state.projectId)}/impact-analysis`, {
        method:"POST", headers:{"Content-Type":"application/json",Accept:"application/json"},
        body:JSON.stringify({object:$("changeObject").value,change_type:$("changeType").value,before:$("beforeValue").value,after:$("afterValue").value})
      });
      renderImpactResult(result);
      $("impactResult").classList.add("show");
      ui.showToast("真实影响分析完成：" + (result.transitive_impacts || []).length);
    } catch (error) { ui.showToast("影响分析失败：" + error.message); }
    finally { button.disabled = false; button.textContent = "重新分析"; }
  }
  function listBlock(title, values, empty) {
    const list = values || [];
    return `<section class="card card-pad"><h3>${escapeHtml(title)} · ${list.length}</h3><div class="evidence-list">${list.length
      ? list.map(value => `<div class="evidence-item">${escapeHtml(typeof value === "string" ? value : JSON.stringify(value))}</div>`).join("")
      : `<div class="empty-guidance">${escapeHtml(empty || "无")}</div>`}</div></section>`;
  }
  function renderImpactResult(result) {
    const direct = result.direct_impacts || [];
    const transitive = result.transitive_impacts || [];
    const scripts = result.scripts || [];
    const metrics = result.metrics || [];
    const ads = result.ads_tables || [];
    const warnings = result.warnings || [];
    const paths = result.paths || [];
    $("impactResult").innerHTML = `<div class="card card-pad"><div class="eyebrow">真实静态分析结果</div><h2>风险等级：${escapeHtml(String(result.risk || "unknown").toUpperCase())}</h2>
      <div class="impact-kpis"><div class="impact-kpi"><strong>${direct.length}</strong><span>直接下游</span></div><div class="impact-kpi"><strong>${transitive.length}</strong><span>全部下游</span></div><div class="impact-kpi"><strong>${scripts.length}</strong><span>相关 SQL</span></div><div class="impact-kpi"><strong>${ads.length}</strong><span>ADS 报表表</span></div></div></div>
      <div class="impact-columns" style="margin-top:14px">${listBlock("受影响链路", paths.map(p => `${p.source} → ${p.target}${p.file ? ` · ${p.file}:${p.line || "?"}` : ""}`), "没有找到下游路径")}${listBlock("受影响对象", (result.affected || []).map(item => `${item.type || "object"} · ${item.object}${item.direct ? " · 直接影响" : ""}`), "没有已证明的受影响对象")}${listBlock("需要检查的 SQL", scripts, "没有关联 SQL 文件")}${listBlock("受影响指标", metrics, "没有识别到关联指标")}${listBlock("受影响 ADS", ads, "没有识别到 ADS 消费表")}${listBlock("风险提示", warnings.map(w => w.message || w.code || w), "当前范围没有额外风险提示")}${listBlock("修改顺序", (result.modification_order || []).map(item => `${item.sequence}. ${item.object} · ${item.action}`), "没有生成对象级修改顺序")}${listBlock("回归建议", result.recommendations || [], "后端未返回修改建议")}</div>`;
  }
  async function runComparison() {
    if (state.mode !== "live") return ui.showToast("分析服务未连接，无法比较版本");
    try {
      const query = new URLSearchParams({left:$("compareLeft").value,right:$("compareRight").value});
      if (!$("compareLeft").value || !$("compareRight").value) throw new Error("请选择两个有效版本");
      const result = await request(`/projects/${encodeURIComponent(state.projectId)}/compare?${query}`);
      renderComparisonResult(result);
      ui.showToast("真实版本语义比较完成");
    } catch (error) { ui.showToast("版本比较失败：" + error.message); }
  }
  function diffLines(values, css, empty) {
    return values && values.length ? values.map(value => `<div class="diff-line ${css}">${escapeHtml(Array.isArray(value) ? value.join(" → ") : value)}</div>`).join("") : `<div class="empty-guidance">${escapeHtml(empty)}</div>`;
  }
  function renderComparisonResult(result) {
    const tables = result.tables || {}, lineage = result.lineage || {};
    $("compareResult").innerHTML = `<div class="eyebrow">v${escapeHtml(result.left)} → v${escapeHtml(result.right)}</div><h2>语义差异</h2><div class="diff-grid" style="margin-top:16px">
      <section class="diff-section"><h3>新增表 · ${(tables.added || []).length}</h3>${diffLines(tables.added,"add","没有新增表")}</section>
      <section class="diff-section"><h3>删除表 · ${(tables.removed || []).length}</h3>${diffLines(tables.removed,"remove","没有删除表")}</section>
      <section class="diff-section"><h3>字段变化 · ${(tables.changed || []).length}</h3>${(tables.changed || []).length ? tables.changed.map(change => `<div class="evidence-item"><strong>${escapeHtml(change.table)}</strong><br>新增：${escapeHtml((change.added_columns || []).map(x => x.join(" ")).join("、") || "无")}<br>删除：${escapeHtml((change.removed_columns || []).map(x => x.join(" ")).join("、") || "无")}</div>`).join("") : '<div class="empty-guidance">没有字段定义变化</div>'}</section>
      <section class="diff-section"><h3>血缘变化</h3><strong class="subtle">新增 ${(lineage.added || []).length}</strong>${diffLines(lineage.added,"add","没有新增血缘")}<strong class="subtle">删除 ${(lineage.removed || []).length}</strong>${diffLines(lineage.removed,"remove","没有删除血缘")}</section>
      </div>`;
  }
  async function loadLineage(level) {
    if (!state.projectId || state.mode !== "live") return;
    try {
      const payload = await request(`/projects/${encodeURIComponent(state.projectId)}/lineage?level=${encodeURIComponent(level)}`);
      const edges = unwrap(payload, ["edges","lineage","data"]);
      if (level === "column") state.columnEdges = edges;
      else state.tableEdges = edges;
      const names = [...new Set(edges.flatMap(edge => [edge.source, edge.target]).filter(Boolean))];
      const models = names.map(name => {
        const table = state.tables.find(item => name === item.name || name.startsWith(item.name + "."));
        return normalizeNode({id:name,name,layer:table?.layer || "OTHER",description:level === "column" ? "字段血缘" : "表级资产"}, 0);
      });
      ui.setNodes(models);
      ui.setEdges(edges);
      ui.renderGraph();
      $("evidenceTitle").textContent = level === "column" ? "字段级血缘" : "表级血缘";
      $("evidenceDesc").innerHTML = `<p>已加载 ${edges.length} 条真实${level === "column" ? "字段" : "表"}血缘。搜索并点击节点可查看 SQL 证据。</p>`;
    } catch (error) {
      $("evidenceTitle").textContent = "血缘加载失败";
      $("evidenceDesc").innerHTML = `<div class="empty-guidance">${escapeHtml(error.message)}</div>`;
      ui.showToast("血缘切换失败：" + error.message);
    }
  }
  async function ask(question) {
    const messages = $("messages");
    messages.insertAdjacentHTML("beforeend", `<div class="msg user">${escapeHtml(question)}</div>`);
    if (state.mode !== "live") {
      messages.insertAdjacentHTML("beforeend", '<div class="msg ai"><div class="avatar">!</div><div class="bubble" style="color:var(--danger)">分析服务未连接，请恢复连接后再提问。</div></div>');
      messages.scrollTop = messages.scrollHeight; return;
    }
    try {
      const answer = await request(`/projects/${encodeURIComponent(state.projectId)}/assistant/query`, {
        method:"POST",headers:{"Content-Type":"application/json",Accept:"application/json"},body:JSON.stringify({question})
      });
      const evidence = unwrap(answer, ["evidence"]);
      messages.insertAdjacentHTML("beforeend", `<div class="msg ai"><div class="avatar">✦</div><div class="bubble">${escapeHtml(answer.answer || answer.message || JSON.stringify(answer)).replace(/\n/g,"<br>")}${evidence.map(item => `<span class="evidence-link">${escapeHtml(item.object || "证据")} · ${escapeHtml(item.file || "文件未知")}${item.line ? ":" + escapeHtml(item.line) : ""}</span>`).join("")}</div></div>`);
    } catch (error) {
      messages.insertAdjacentHTML("beforeend", `<div class="msg ai"><div class="avatar">!</div><div class="bubble" style="color:var(--danger)">真实问答失败：${escapeHtml(error.message)}</div></div>`);
    }
    messages.scrollTop = messages.scrollHeight;
  }

  const packageTrees = {
    minimum: `data-project/
├── ddl/                         [推荐]
│   └── all_tables.sql           [推荐]
└── sql/                         [必需]
    ├── 01_ods_to_dwd.sql        [必需]
    └── 02_dwd_to_dws.sql        [必需]`,
    recommended: `data-project/
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
    ├── ods_sample.csv
    └── dwd_sample.csv`
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
    $("wizardMode").textContent = state.mode === "live" ? "● 分析服务已连接：文件会执行预检与分析"
      : "分析服务未连接：请先重新连接";
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
  function downloadCsv(filename, rows) {
    const csvCell = value => `"${String(value == null ? "" : value).replace(/"/g, '""')}"`;
    const body = "\ufeff" + rows.map(row => row.map(csvCell).join(",")).join("\r\n");
    const url = URL.createObjectURL(new Blob([body], {type:"text/csv;charset=utf-8"}));
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }
  function exportFieldDictionary() {
    const rows = [["表名","层级","数据粒度","核心时间字段","字段名","字段类型","语义角色","置信度","DDL文件"]];
    state.tables.forEach(table => {
      const columns = table.columns.length ? table.columns : [{}];
      columns.forEach(column => rows.push([table.name,table.layer,table.grain,table.time,column.name,column.type,column.role || column.semantic_type,column.confidence,table.ddlFile]));
    });
    downloadCsv("字段字典.csv", rows);
    ui.showToast(`已导出 ${Math.max(0, rows.length - 1)} 条真实字段记录`);
  }
  function exportMetricDictionary() {
    const rows = [["指标名","产出表","公式","粒度","过滤条件","SQL文件","行号"]];
    state.metrics.forEach(metric => rows.push([metric.name,metric.table,metric.formula,(metric.grain || []).join(" + "),metric.filter,metric.file,metric.line]));
    downloadCsv("指标字典.csv", rows);
    ui.showToast(`已导出 ${state.metrics.length} 条真实指标记录`);
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
  $("refreshBtn").onclick = () => state.mode === "live" ? loadProjectData() : loadProjects();
  $("projectSelect").onchange = event => { state.projectId = event.target.value; loadProjectData(); };
  $("importBtn").onclick = openWizard;
  $("emptyCreateBtn").onclick = openWizard;
  $("emptyRetryBtn").onclick = () => state.projectId ? loadProjectData() : loadProjects();
  $("projectMenuBtn").onclick = openProjectManagement;
  $("projectDrawerClose").onclick = closeProjectManagement;
  $("manageImportBtn").onclick = () => { closeProjectManagement(); openWizard(); };
  $("refreshHistoryBtn").onclick = refreshHistory;
  $("reanalyzeBtn").onclick = reanalyzeLatest;
  $("deleteProjectBtn").onclick = deleteCurrentProject;
  $("projectDrawer").onclick = event => { if (event.target === $("projectDrawer")) closeProjectManagement(); };
  $("historyList").onclick = event => {
    const button = event.target.closest("[data-diagnostic-index]");
    if (!button) return;
    const item = state.versions[Number(button.dataset.diagnosticIndex)];
    if (item) openDiagnostic(item, button);
  };
  $("projectDrawer").addEventListener("keydown", event => {
    if (event.key === "Escape") closeProjectManagement();
    if (event.key === "Tab") {
      const focusable = [...$("projectDrawer").querySelectorAll('button:not([hidden]):not([disabled]),input:not([hidden]),select:not([hidden])')].filter(el => el.offsetParent !== null);
      if (!focusable.length) return;
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });
  $("diagnosticClose").onclick = closeDiagnostic;
  $("diagnosticDone").onclick = closeDiagnostic;
  $("copyDiagnostic").onclick = copyDiagnostic;
  $("diagnosticDialog").onclick = event => { if (event.target === $("diagnosticDialog")) closeDiagnostic(); };
  $("diagnosticDialog").addEventListener("keydown", event => {
    if (event.key === "Escape") {
      event.stopPropagation();
      closeDiagnostic();
    }
    if (event.key === "Tab") {
      const focusable = [...$("diagnosticDialog").querySelectorAll('button:not([hidden]):not([disabled])')].filter(el => el.offsetParent !== null);
      if (!focusable.length) return;
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });
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
    if (state.mode !== "live") return ui.showToast("分析服务未连接，暂时无法下载模板");
    location.href = apiRoot + "/templates/blank";
  };
  $("gotoAssets").onclick = () => { closeWizard(); ui.navigate("assets"); };
  $("gotoLineage").onclick = () => { closeWizard(); ui.navigate("lineage"); };
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
  renderPackageTree(params.get("package") === "recommended" ? "recommended" : "minimum");
  $("runImpact").onclick = runImpact;
  $("runCompare").onclick = runComparison;
  $("exportFields").onclick = exportFieldDictionary;
  $("exportMetrics").onclick = exportMetricDictionary;
  window.addEventListener("dfi:lineage-mode", event => loadLineage(event.detail.mode));
  $("sendChat").onclick = () => { const input=$("chatInput"), value=input.value.trim(); if(value){input.value="";ask(value);} };
  $("chatInput").onkeydown = event => { if(event.key === "Enter") $("sendChat").click(); };
  document.querySelectorAll(".suggestion").forEach(item => item.onclick = () => ask(item.textContent.trim()));
  showWorkspaceState("loading", {
    kicker: "正在启动工作台", title: "正在连接分析服务", message: "正在读取本机项目和分析结果。",
    create: false, retry: false, foot: apiRoot
  });
  loadProjects();
  const wizardDeepLink = Number(params.get("wizard"));
  if (wizardDeepLink >= 1 && wizardDeepLink <= 4) {
    setTimeout(() => {
      openWizard();
      setWizardStep(wizardDeepLink);
    }, 250);
  }
}());
