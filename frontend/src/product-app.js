(function () {
  "use strict";

  const params = new URLSearchParams(location.search);
  const suppliedRoot = params.get("api");
  const apiRoot = (suppliedRoot || (location.protocol === "file:" ? "http://127.0.0.1:18080/api" : location.origin + "/api")).replace(/\/+$/, "");
  const state = { mode: "connecting", projectId: null, projects: [], versions: [], wizardStep: 1, preflight: null, importResult: null };
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
      const detail = body && (body.detail || body.error || body.message);
      throw new Error(typeof detail === "string" ? detail : "HTTP " + response.status);
    }
    return body;
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
      risk: Boolean(t.risk || t.has_risk || t.status === "warning")
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
      x: 8 + lane * 152,
      y: 45 + inLane * 150,
      n: escapeHtml(n.qualified_name || n.qualifiedName || n.name),
      l: layer === "RDS" ? "SOURCE" : layer,
      d: escapeHtml(n.description || n.desc || "数据资产")
    };
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
      request(`/projects/${id}/imports`)
    ]);
    const failures = results.filter(r => r.status === "rejected");
    const tableList = results[0].status === "fulfilled" ? unwrap(results[0].value, ["tables","items","data"]) : [];
    if (tableList.length) {
      ui.setTables(tableList.map(normalizeTable));
      ui.renderAssets();
    }
    const lineagePayload = results[1].status === "fulfilled" ? results[1].value : null;
    let rawNodes = unwrap(lineagePayload, ["nodes","tables","items"]);
    const rawEdges = unwrap(lineagePayload, ["edges","lineage","data"]);
    if (!rawNodes.length && rawEdges.length) {
      const tableMap = new Map(tableList.map(t => [t.name, t]));
      const names = [...new Set(rawEdges.flatMap(e => [e.source, e.target]))];
      rawNodes = names.map(name => Object.assign({id:name,name}, tableMap.get(name) || {}));
    }
    if (rawNodes.length) {
      ui.setNodes(rawNodes.slice(0, 12).map(normalizeNode));
      ui.setEdges(rawEdges);
      ui.renderGraph();
    }
    const metricList = results[3].status === "fulfilled" ? unwrap(results[3].value, ["metrics","items","data"]) : [];
    if (metricList.length) {
      ui.setMetrics(metricList.map(normalizeMetric));
      ui.renderMetrics();
    }
    state.versions = results[5].status === "fulfilled" ? unwrap(results[5].value, ["imports","versions","items","data"]) : [];
    const workflowPayload = results[2].status === "fulfilled" ? results[2].value : null;
    const jobs = unwrap(workflowPayload, ["jobs","items","data"]);
    const findingPayload = results[4].status === "fulfilled" ? results[4].value : null;
    const findings = unwrap(findingPayload, ["findings","risks","items","data"]);
    updateLiveSummaries(tableList, jobs, findings, metricList);
    updateVersions();
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
        body:JSON.stringify({object:$("changeObject").value,change_type:$("changeType").value,before:$("beforeValue").value,after:$("afterValue").value})
      });
      $("impactResult").classList.add("show");
      ui.showToast("真实影响分析完成：" + (result.affected_count ?? result.total_affected ?? "结果已返回"));
    } catch (error) { ui.showToast("影响分析失败：" + error.message); }
    finally { button.disabled = false; button.textContent = "重新分析"; }
  }
  async function runComparison() {
    if (state.mode !== "live") return ui.showToast("当前为演示版本比较，未调用后端");
    try {
      const query = new URLSearchParams({left:$("compareLeft").value,right:$("compareRight").value});
      await request(`/projects/${encodeURIComponent(state.projectId)}/compare?${query}`);
      ui.showToast("真实版本语义比较完成");
    } catch (error) { ui.showToast("版本比较失败：" + error.message); }
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
  $("sendChat").onclick = () => { const input=$("chatInput"), value=input.value.trim(); if(value){input.value="";ask(value);} };
  $("chatInput").onkeydown = event => { if(event.key === "Enter") $("sendChat").click(); };
  document.querySelectorAll(".suggestion").forEach(item => item.onclick = () => ask(item.textContent.trim()));
  loadProjects();
  const wizardDeepLink = Number(params.get("wizard"));
  if (wizardDeepLink >= 1 && wizardDeepLink <= 4) {
    setTimeout(() => {
      openWizard();
      setWizardStep(wizardDeepLink);
    }, 250);
  }
}());
