export const APP_SHELL = String.raw`
  <div class="app">
    <aside class="sidebar" id="sidebar">
      <div class="brand"><div class="brand-mark"></div><div><strong>DataFlow Inspector</strong><small>数据加工链路分析台</small></div></div>
      <nav class="nav" aria-label="主导航">
        <div class="nav-label">工作台</div>
        <button class="active" data-page="overview"><span class="ico">⌂</span>项目总览</button>
        <button data-page="assets"><span class="ico">▦</span>数据资产</button>
        <button data-page="lineage"><span class="ico">⌘</span>血缘分析</button>
        <button data-page="workflow"><span class="ico">⌁</span>作业流</button>
        <button data-page="metrics"><span class="ico">◫</span>指标口径</button>
        <div class="nav-label">变更与诊断</div>
        <button data-page="imports"><span class="ico">⇧</span>导入历史</button>
        <button data-page="impact"><span class="ico">⌬</span>变更影响</button>
        <button data-page="compare"><span class="ico">⇄</span>版本比较</button>
        <button data-page="assistant"><span class="ico">✦</span>数据助手</button>
      </nav>
      <div class="side-foot"><div class="status"><span class="dot" id="sideDot"></span><span id="sideVersion">正在连接分析服务…</span></div><div id="sideStats" style="font-size:10px;color:#7890a8;margin-top:8px">读取项目元数据</div></div>
    </aside>
    <main class="main">
      <header class="topbar">
        <div class="project-switch"><button class="btn icon-btn mobile-menu" id="menuBtn" aria-label="打开导航">☰</button><div><small>当前项目</small><br><select id="projectSelect" class="project-select" aria-label="切换项目"><option>正在加载项目…</option></select></div></div>
        <div class="top-actions"><span class="connection-pill loading" id="connectionPill">连接中</span><button class="btn icon-btn" id="refreshBtn" title="刷新后端数据" aria-label="刷新后端数据">↻</button><button class="btn" id="tableImportBtn">＋ 单表导入</button><button class="btn" id="importBtn">＋ 导入项目包</button><button class="btn primary" data-goto="assistant">✦ 问数据助手</button></div>
      </header>
      <div class="mode-banner" id="modeBanner"><div><strong id="modeBannerTitle">连接失败</strong><span id="modeBannerText">无法读取后端，尚未切换为演示数据。</span> <code id="apiEndpoint"></code></div><div style="display:flex;gap:8px"><button class="btn" id="demoModeBtn">显式切换演示模式</button><button class="btn" id="retryConnection">重新连接</button></div></div>
      <div class="content">
        <div class="pipeline" aria-label="数据加工层级">
          <div class="pipe-stage"><div class="pipe-node" style="--c:var(--source)" data-layer="SOURCE"><i></i>RDS / CDM <small>3</small></div><span class="pipe-line pulse"></span></div>
          <div class="pipe-stage"><div class="pipe-node" style="--c:var(--ods)" data-layer="ODS"><i></i>ODS <small>2</small></div><span class="pipe-line pulse"></span></div>
          <div class="pipe-stage"><div class="pipe-node" style="--c:var(--dwd)" data-layer="DWD"><i></i>DWD <small>3</small></div><span class="pipe-line pulse"></span></div>
          <div class="pipe-stage"><div class="pipe-node" style="--c:var(--dws)" data-layer="DWS"><i></i>DWS 分钟 / 小时 <small>3</small></div><span class="pipe-line pulse"></span></div>
          <div class="pipe-stage"><div class="pipe-node" style="--c:var(--ads)" data-layer="ADS"><i></i>ADS 报表 <small>3</small></div></div>
        </div>

        <section class="page active" id="page-overview">
          <div class="page-head"><div><div class="eyebrow">Project pulse</div><h1>数据加工项目</h1><div class="subtle">选择项目并完成真实分析后展示项目概览。</div></div><div class="head-actions"><button class="btn" data-goto="compare">比较版本</button><button class="btn primary" data-goto="lineage">打开完整血缘</button></div></div>
          <div class="grid cols-4">
            <div class="card stat" style="--tint:#e8f1fb"><div class="label">数据资产</div><div class="value">0</div><div class="delta">等待真实分析结果</div></div>
            <div class="card stat" style="--tint:#efeafd"><div class="label">字段总数</div><div class="value">0</div><div class="delta">等待真实分析结果</div></div>
            <div class="card stat" style="--tint:#fff0df"><div class="label">指标口径</div><div class="value">0</div><div class="delta">等待真实分析结果</div></div>
            <div class="card stat" style="--tint:#ffe7e9"><div class="label">待处理风险</div><div class="value" style="color:var(--danger)">0</div><div class="delta">等待真实分析结果</div></div>
          </div>
          <div class="grid two" style="margin-top:16px">
            <div class="card"><div class="section-head"><h2>作业流概览</h2><a data-goto="workflow">查看作业拓扑 →</a></div><div class="flow-list"><div class="empty-shell"><strong>暂无作业流</strong>等待真实项目分析结果。</div></div></div>
            <div class="card"><div class="section-head"><h2>需要关注</h2><a data-goto="impact">进入诊断 →</a></div><div class="risk-list"><div class="empty-shell"><strong>暂无风险结果</strong>等待真实项目分析结果。</div></div></div>
          </div>
        </section>

        <section class="page" id="page-assets">
          <div class="page-head"><div><div class="eyebrow">Data catalog</div><h1>数据资产</h1><div class="subtle">按项目隔离查看表资产，支持按业务线、加工层级和风险筛选。</div></div><div class="head-actions"><button class="btn" id="assetTableImportBtn">单表导入</button><button class="btn" id="exportAssetDictionaryBtn">导出字段字典</button></div></div>
          <div class="toolbar"><div class="search"><input id="assetSearch" placeholder="搜索库表、字段、中文含义或脚本路径" /></div><select id="layerFilter"><option value="">全部层级</option><option>ODS</option><option>DWD</option><option>DWS</option><option>ADS</option><option>DIM</option></select><select id="assetFlowFilter"><option value="">全部业务线</option></select><label style="font-size:11px;color:var(--muted)"><input id="riskOnly" type="checkbox" /> 仅看有风险</label></div>
          <div class="toolbar bulk"><div class="bulk-panel"><strong id="assetSelectionSummary">未选中资产</strong><small>支持批量补充负责人、频率与备注草稿；仅作用于当前页面，可随导出一起带走。</small></div><div class="head-actions"><button class="btn" id="bulkEditBtn">批量编辑</button><button class="btn" id="bulkImpactBtn">批量影响分析</button><button class="btn" id="bulkExportBtn">导出已选</button></div></div>
          <div class="card table-card"><table><thead><tr><th class="selection-cell"><input id="assetSelectAll" type="checkbox" aria-label="全选当前资产" /></th><th>资产</th><th>分区 / 粒度</th><th>上游表</th><th>ETL / DDL</th><th>负责人 / 更新</th><th>字段 / 关系</th><th>状态</th></tr></thead><tbody id="assetRows"></tbody></table></div>
        </section>

        <section class="page" id="page-detail">
          <div class="page-head"><div><div class="eyebrow" id="detailEyebrow">Table detail</div><h1 class="mono" id="detailTitle">请选择一张表</h1><div class="subtle" id="detailSubtitle">从数据资产页或血缘图进入后，这里会展示该表的真实结构、字段来源和加工证据。</div></div><div class="head-actions"><button class="btn" id="detailLineageBtn">查看血缘</button><button class="btn" id="detailExportBtn">导出详情</button><button class="btn" id="detailSaveBtn">保存元数据</button><button class="btn primary" id="detailImpactBtn">分析变更</button></div></div>
          <div class="detail-layout">
            <div>
              <div class="card"><div class="info-grid">
                <div class="info-item"><small>数据层级</small><strong id="detailLayer"><span class="tag" style="--tag:#55718c">—</span></strong></div>
                <div class="info-item"><small>数据粒度</small><strong id="detailGrain">—</strong></div>
                <div class="info-item"><small>解析来源</small><strong id="detailParseSource">—</strong></div>
                <div class="info-item"><small>核心时间</small><strong class="mono" id="detailTimeFields">—</strong></div>
                <div class="info-item"><small>直接上游</small><strong id="detailUpstreamCount">—</strong></div>
                <div class="info-item"><small>直接下游</small><strong id="detailDownstreamCount">—</strong></div>
              </div><div class="meta-editor"><div class="field"><label for="detailDisplayName">中文名 / 展示名</label><input id="detailDisplayName" placeholder="可编辑展示名"></div><div class="field"><label for="detailOwner">负责人</label><input id="detailOwner" placeholder="负责人"></div><div class="field"><label for="detailFrequency">更新频率</label><input id="detailFrequency" placeholder="如：每 5 分钟"></div><div class="field"><label for="detailRetention">留存期</label><input id="detailRetention" placeholder="如：90 天"></div><div class="field full"><label for="detailNote">表备注 / 业务含义</label><textarea id="detailNote" placeholder="补充表级业务说明、口径说明或注意事项"></textarea></div><div class="field full"><div class="focus-tip" id="detailDraftHint"><strong>提示：</strong>字段备注与表级元数据会集中提交保存，不逐行自动写入。</div></div></div><div class="tabs"><button class="tab active">字段</button><button class="tab">加工逻辑</button><button class="tab">上下游</button><button class="tab">指标</button><button class="tab">风险</button></div><div class="table-card"><table><thead><tr><th>字段</th><th>类型</th><th>标签</th><th>来源</th><th>加工逻辑</th><th>业务备注</th></tr></thead><tbody id="detailFieldRows">
                <tr><td colspan="6"><div class="empty-shell"><strong>尚未选择表</strong>请从数据资产页或血缘图打开表详情。</div></td></tr>
              </tbody></table></div><div class="card card-pad" style="margin:16px;border:1px dashed #d6dfe6;background:#fbfdfe"><h3>与上一版本差异</h3><div id="detailDiff"><div class="empty-shell"><strong>暂无差异摘要</strong>如果当前表在版本比较中发生变化，这里会展示字段和结构 diff。</div></div></div><div class="grid two" style="padding:16px;border-top:1px solid var(--line)"><div class="card card-pad"><h3>指标口径</h3><div id="detailMetrics"><div class="empty-shell"><strong>暂无指标</strong>该表如产出指标，这里会展示真实公式和粒度。</div></div></div><div class="card card-pad"><h3>加工操作</h3><div id="detailOperations"><div class="empty-shell"><strong>暂无操作摘要</strong>该表关联的写入操作、分组和过滤条件会展示在这里。</div></div></div></div></div>
            </div>
            <aside><div class="card card-pad"><h3>版本信息</h3><div id="detailVersion"><div class="empty-shell"><strong>暂无版本</strong>选中真实表后展示分析版本、导入文件和状态。</div></div></div><div class="card card-pad" style="margin-top:14px"><h3>加工证据</h3><div id="detailEvidence"><div class="empty-shell"><strong>暂无证据</strong>选中真实表后展示 DDL、ETL 和行号证据。</div></div></div><div class="card card-pad" style="margin-top:14px"><h3>质量提示</h3><div id="detailRisks"><div class="empty-shell"><strong>暂无风险</strong>若该表命中过滤漂移、时间口径或 SELECT * 风险，这里会列出。</div></div></div><div class="card card-pad" style="margin-top:14px"><h3>上下游</h3><div id="detailRelations"><div class="empty-shell"><strong>暂无关系</strong>选中真实表后展示上游、下游与指标数量。</div></div></div></aside>
          </div>
        </section>

        <section class="page" id="page-lineage">
          <div class="page-head"><div><div class="eyebrow">Lineage explorer</div><h1>血缘分析</h1><div class="subtle">从来源、转换表达式到最终报表，逐层验证每一条加工关系。</div></div></div>
          <div class="toolbar lineage-toolbar"><select id="lineageMode"><option>表级血缘</option><option>字段级血缘</option></select><select id="lineageDepth"><option>上下游 3 层</option><option>上下游 5 层</option><option>仅直接关系</option></select><div class="search"><input id="lineageSearch" placeholder="定位表或字段" /></div><button class="btn" id="lineageFocusBtn">聚焦当前对象</button><button class="btn" id="highlightPath">高亮主链路</button><span class="focus-tip" id="lineageFocusHint">尚未指定聚焦对象</span></div>
          <div class="card lineage-shell"><div class="graph"><div class="lane-labels"><span>RDS / CDM</span><span>ODS</span><span>DWD</span><span>DWS</span><span>ADS</span></div><div class="graph-area" id="graphArea"></div></div><aside class="evidence"><div class="evidence-head"><div class="eyebrow">Selected relation</div><h3 id="evidenceTitle">尚未选择血缘节点</h3></div><div class="evidence-body"><div class="evidence-block"><label>节点说明</label><p id="evidenceDesc">选择真实血缘节点后展示其说明。</p></div><div class="evidence-block"><label>数据粒度</label><p id="evidenceGrain">—</p></div><div class="evidence-block"><label>加工脚本</label><p class="mono" id="evidenceScript">—</p></div><div class="evidence-block"><label>核心关系</label><div class="code" id="evidenceRelation">—</div></div><button class="btn primary" style="width:100%" data-goto="detail">打开表详情</button></div></aside></div>
        </section>

        <section class="page" id="page-workflow">
          <div class="page-head"><div><div class="eyebrow">Workflow reconstruction</div><h1>作业流</h1><div class="subtle">根据 SQL 读写关系重建加工顺序，并区分已确认与自动推断依赖。</div></div><div class="head-actions"><button class="btn">确认全部可靠依赖</button></div></div>
          <div class="toolbar"><select><option>Token 请求主链</option><option>业务维度补充</option><option>报表应用层</option></select><span class="subtle" style="font-size:11px">● 实线：已确认　◌ 虚线：自动推断</span></div>
          <div class="card workflow-canvas"><div class="empty-shell"><strong>暂无作业流</strong>等待真实项目分析结果。</div></div>
          <div class="grid cols-3" style="margin-top:16px"><div class="card card-pad"><div class="eyebrow">6 jobs</div><h3>主链完整</h3><p class="subtle">所有写入表均存在上游来源。</p></div><div class="card card-pad"><div class="eyebrow" style="color:var(--warning)">1 inferred</div><h3>待确认依赖</h3><p class="subtle">分钟聚合 → 小时聚合尚无调度证据。</p></div><div class="card card-pad"><div class="eyebrow" style="color:var(--success)">0 cycles</div><h3>无循环依赖</h3><p class="subtle">当前 DAG 可以正常排序。</p></div></div>
        </section>

        <section class="page" id="page-metrics">
          <div class="page-head"><div><div class="eyebrow">Metric registry</div><h1>指标口径</h1><div class="subtle">技术公式、统计粒度、时间口径和最终消费位置统一管理。</div></div><div class="head-actions"><button class="btn" id="metricExportBtn">导出指标字典</button></div></div>
          <div class="toolbar"><div class="search"><input id="metricSearch" placeholder="搜索指标名称或字段" /></div><select id="metricGrainFilter"><option value="">全部时间粒度</option><option value="分钟">分钟</option><option value="小时">小时</option><option value="天">天</option></select><select id="metricStatusFilter"><option value="">全部状态</option><option value="已确认">已确认</option><option value="待确认">待确认</option></select></div>
          <div class="metric-grid" id="metricGrid"></div>
        </section>

        <section class="page" id="page-imports">
          <div class="page-head"><div><div class="eyebrow">Import operations</div><h1>导入历史与诊断</h1><div class="subtle">查看真实导入状态、分析摘要与失败原因；处理中任务会在本页继续轮询。</div></div><div class="head-actions"><button class="btn" id="refreshImportsBtn">刷新状态</button><button class="btn primary" id="importsUploadBtn">导入项目包</button></div></div>
          <div class="grid cols-4" id="importHistorySummary"><div class="card stat"><div class="label">全部版本</div><div class="value">0</div></div><div class="card stat"><div class="label">处理中</div><div class="value">0</div></div><div class="card stat"><div class="label">已完成</div><div class="value">0</div></div><div class="card stat"><div class="label">失败</div><div class="value">0</div></div></div>
          <div class="card table-card" style="margin-top:16px"><table><thead><tr><th>版本 / 文件</th><th>状态</th><th>分析摘要</th><th>文件数</th><th>创建 / 完成时间</th><th>诊断</th></tr></thead><tbody id="importHistoryRows"><tr><td colspan="6"><div class="empty-shell"><strong>尚未加载导入历史</strong>选择真实项目后刷新。</div></td></tr></tbody></table></div>
        </section>

        <section class="page" id="page-impact">
          <div class="page-head"><div><div class="eyebrow">Change intelligence</div><h1>变更影响分析</h1><div class="subtle">提交一个拟议变更，查看结构、语义和历史回刷影响。不会执行生产变更。</div></div></div>
          <div class="grid two"><div class="card"><div class="section-head"><h2>定义变更</h2><span class="health ok">只读分析</span></div><div class="impact-form"><div class="field full"><label>快捷案例</label><select id="quickCase"><option value="region">修改 region_code 字段长度</option><option value="source">新增 source_type 维度字段</option><option value="logic">调整 success_rate 过滤口径</option></select></div><div class="field full"><label>变更对象</label><input id="changeObject" class="mono" value="dwd.dwd_token_request.region_code" /></div><div class="field"><label>变更类型</label><select id="changeType"><option>字段类型变化</option><option>新增字段</option><option>加工逻辑变化</option></select></div><div class="field"><label>分析范围</label><select><option>完整下游链路</option><option>直接下游</option></select></div><div class="field"><label>修改前</label><input id="beforeValue" class="mono" value="VARCHAR(16)" /></div><div class="field"><label>修改后</label><input id="afterValue" class="mono" value="VARCHAR(32)" /></div><div class="field full"><div class="table-desc" id="impactContext">可从表详情或版本比较直接带入对象与字段 diff。</div></div><div class="field full"><button class="btn primary" id="runImpact">开始分析影响</button></div></div></div>
            <div class="card card-pad"><h3>分析范围</h3><p class="subtle">系统会沿字段级血缘遍历所有传递下游，并检查 SQL 表达式、指标粒度、时间窗口和历史分区。</p><div class="risk"><div class="risk-icon">i</div><div><strong>静态分析边界</strong><p>未导入的 BI、Shell 和动态 SQL 消费方会标记为未知风险。</p></div></div></div></div>
          <div class="impact-summary" id="impactResult"><div class="risk-score"><div class="score-circle"><strong id="impactScore">—</strong></div><div><div class="eyebrow" id="impactRiskLabel">等待分析</div><h2 id="impactHeadline">尚未生成影响结果</h2><div class="subtle" id="impactSummaryText">提交左侧变更后，将在此展示后端返回的真实分析。</div></div></div><div class="grid two" style="margin-top:16px"><div class="card"><div class="section-head"><h2>影响传播路径</h2><a href="#" id="impactOpenLineage">在血缘图中打开 →</a></div><div class="impact-tree" id="impactTree"><div class="empty-shell"><strong>暂无传播路径</strong>完成真实分析后展示。</div></div></div><div class="card"><div class="section-head"><h2>推荐修改顺序</h2></div><div class="flow-list" id="impactRecommendations"><div class="empty-shell"><strong>暂无建议</strong>完成真实分析后展示。</div></div></div></div><div class="card card-pad" style="margin-top:16px"><div class="section-head"><h2>差异证据</h2><span class="subtle" id="impactEvidenceScope">未带入版本证据</span></div><div id="impactEvidenceList"><div class="empty-shell"><strong>暂无证据</strong>从版本比较或元数据修订比较进入时，这里会展示命中的差异项。</div></div></div></div>
        </section>

        <section class="page" id="page-compare">
          <div class="page-head"><div><div class="eyebrow">Semantic diff</div><h1>版本比较</h1><div class="subtle">展示结构、血缘、指标和风险的真实差异，并带版本摘要和诊断信息。</div></div><div class="head-actions"><button class="btn" id="exportCompareBtn">导出比较结果</button></div></div>
          <div class="toolbar"><select id="compareLeft"><option value="">暂无可比较版本</option></select><span>→</span><select id="compareRight"><option value="">暂无可比较版本</option></select><button class="btn primary" id="runCompare" disabled>重新比较</button></div>
          <div class="grid cols-4" id="compareSummaryCards"><div class="card stat" style="--tint:#e6f5ee"><div class="label">新增</div><div class="value" style="color:var(--success)">0</div></div><div class="card stat" style="--tint:#fff0df"><div class="label">修改</div><div class="value" style="color:var(--warning)">0</div></div><div class="card stat" style="--tint:#ffe9eb"><div class="label">删除</div><div class="value" style="color:var(--danger)">0</div></div><div class="card stat" style="--tint:#e8f1fb"><div class="label">受影响 ADS</div><div class="value">0</div></div></div>
          <div class="grid two" style="margin-top:16px">
            <div class="card card-pad" id="compareVersionMeta"><div class="load-state"><strong>请选择两个版本</strong>这里会显示版本摘要、告警和导入诊断。</div></div>
            <div class="card card-pad" id="compareChangeList"><div class="load-state"><strong>等待比较</strong>点击“重新比较”后渲染结构化差异。</div></div>
          </div>
        </section>

        <section class="page" id="page-assistant">
          <div class="page-head"><div><div class="eyebrow">Evidence-grounded assistant</div><h1>数据助手</h1><div class="subtle">基于已解析的表、字段、SQL 和血缘回答，并给出可追溯证据。</div></div></div>
          <div class="card chat"><aside class="chat-side"><h3 style="margin-bottom:14px">建议提问</h3><div class="suggestion">当前项目有哪些高风险问题？</div><div class="suggestion">哪些表使用 event_time？</div><div class="suggestion">某个字段会影响哪些下游？</div></aside><div class="chat-main"><div class="messages" id="messages"><div class="empty-shell"><strong>暂无对话</strong>输入问题后将调用真实项目助手。</div></div><div class="chat-input"><input id="chatInput" placeholder="询问字段来源、指标口径或变更影响…" /><button class="btn primary" id="sendChat">发送</button></div></div></div>
        </section>
      </div>
    </main>
  </div>

  <div class="drawer-overlay" id="drawer" role="dialog" aria-modal="true" aria-labelledby="wizardTitle"><div class="drawer import-drawer">
    <div class="wizard-head"><button class="drawer-close" aria-label="关闭导入向导">×</button><div class="eyebrow">Import readiness</div><h2 id="wizardTitle">导入项目资料</h2><div class="wizard-mode" id="wizardMode">正在确认连接模式</div>
      <div class="wizard-steps" aria-label="导入进度">
        <div class="wizard-step active" data-wstep="1"><i></i><strong>项目</strong><span>选择归属</span></div>
        <div class="wizard-step" data-wstep="2"><i></i><strong>准备</strong><span>了解目录</span></div>
        <div class="wizard-step" data-wstep="3"><i></i><strong>检查</strong><span>上传前预检</span></div>
        <div class="wizard-step" data-wstep="4"><i></i><strong>分析</strong><span>确认并完成</span></div>
      </div>
    </div>
    <div class="wizard-body">
      <section class="wizard-panel active" data-wpanel="1">
        <h3>这批资料属于哪个项目？</h3><p class="subtle">相关作业流如果会互相引用表，建议放进同一个项目，跨链路血缘才能自动连接。</p>
        <div class="choice-grid">
          <label class="choice-card"><input type="radio" name="projectMode" value="existing" checked><strong>加入现有项目</strong><p>作为当前项目的一个新分析版本。</p></label>
          <label class="choice-card"><input type="radio" name="projectMode" value="new"><strong>创建新项目</strong><p>适合独立业务域或第一批资料。</p></label>
        </div>
        <div class="field" id="existingProjectField"><label for="wizardProjectSelect">选择项目</label><select id="wizardProjectSelect"><option value="">正在读取项目…</option></select></div>
        <div class="field" id="newProjectField" hidden><label for="importProjectName">项目名称</label><input id="importProjectName" placeholder="例如：Token 请求流量分析" autocomplete="off"></div>
        <div class="field" style="margin-top:12px"><label for="importVersionNote">版本说明（可选）</label><input id="importVersionNote" placeholder="例如：增加 source_type 维度"></div>
      </section>
      <section class="wizard-panel" data-wpanel="2">
        <h3>按这个结构准备项目包</h3><p class="subtle">DDL 与加工 SQL 是核心输入；作业清单和少量脱敏样例会提高顺序与字段语义判断的准确度。</p>
        <div class="package-tabs"><button class="btn package-tab active" data-package="minimum">最小可用</button><button class="btn package-tab" data-package="recommended">推荐完整</button></div>
        <div class="package-tree" id="packageTree" aria-live="polite"></div>
        <div class="legend"><span><b style="background:#7dd5df"></b>必需</span><span><b style="background:#f1bc73"></b>推荐</span><span><b style="background:#8fa4b8"></b>可选</span></div>
        <div class="download-row"><button class="btn" id="downloadBlankTemplate">↓ 下载空白模板</button><button class="btn" id="downloadDemoPackage">↓ 下载演示项目包</button></div>
        <p class="wizard-help">不要上传全量生产数据、数据库账号、密钥或调度平台密码。样例数据建议每表 20～100 行并提前脱敏。</p>
      </section>
      <section class="wizard-panel" data-wpanel="3">
        <h3>选择 ZIP 并执行上传前检查</h3><p class="subtle">预检只检查包结构和可识别内容，不创建分析版本。只有后端真实返回的结果才会标记为通过。</p>
        <label class="upload-zone" for="importFile"><input id="importFile" type="file" accept=".zip"><strong>点击选择 ZIP 项目包</strong><span class="subtle">仅接受 .zip；建议包含 ddl/ 与 sql/</span></label>
        <div class="file-meta" id="fileMeta"><div class="file-icon">ZIP</div><div><strong id="fileName">—</strong><small id="fileSize">—</small></div><button class="btn" id="replaceFile" style="margin-left:auto">重新选择</button></div>
        <div class="preflight" id="preflightArea"><div class="load-state"><strong>尚未执行预检</strong>选择文件后，点击“检查项目包”。</div></div>
      </section>
      <section class="wizard-panel" data-wpanel="4">
        <div id="importConfirm">
          <h3>确认上传并开始分析</h3><p class="subtle">系统将保存一个新版本，解析 DDL、SQL、字段血缘、指标和作业依赖。分析过程不会执行上传的 SQL。</p>
          <div class="confirm-box"><div class="confirm-row"><span>目标项目</span><strong id="confirmProject">—</strong></div><div class="confirm-row"><span>项目包</span><strong id="confirmFile">—</strong></div><div class="confirm-row"><span>预检状态</span><strong id="confirmPreflight">—</strong></div><div class="confirm-row"><span>版本说明</span><strong id="confirmNote">—</strong></div></div>
        </div>
        <div id="importComplete" hidden><div class="eyebrow">Analysis complete</div><h3>项目版本已完成分析</h3><p class="subtle" id="completeText">后端已返回本次分析摘要。</p><div class="summary-grid" id="importSummary"></div><div class="download-row"><button class="btn primary" id="gotoAssets">进入数据资产</button><button class="btn" id="gotoLineage">查看血缘图</button></div></div>
        <div class="import-progress" id="importProgress" role="status" aria-live="polite"></div>
      </section>
      <div class="drawer-actions"><button class="btn" id="wizardBack">上一步</button><button class="btn" id="wizardCancel">取消</button><button class="btn primary" id="wizardNext">下一步</button></div>
    </div>
  </div></div>
  <div class="drawer-overlay" id="tableDrawer" role="dialog" aria-modal="true" aria-labelledby="tableDrawerTitle"><div class="drawer" style="width:min(780px,96vw)">
    <div class="drawer-shell">
      <button class="drawer-close" id="tableDrawerClose" aria-label="关闭单表导入">×</button>
      <div class="eyebrow">Single table import</div>
      <h2 id="tableDrawerTitle">按表导入 DDL / ETL</h2>
      <div class="subtle">用于补录单张表、补交 DDL，或基于单段 ETL 补齐局部血缘。</div>
      <div class="field"><label for="tableConflictStrategy">冲突策略</label><select id="tableConflictStrategy"><option value="check">先预览并检测冲突</option><option value="replace">覆盖已有表定义</option><option value="keep">保留已有版本，忽略本次导入</option><option value="merge">合并字段与血缘</option></select></div>
      <div class="field"><label for="tableDdlInput">DDL（必填）</label><textarea id="tableDdlInput" placeholder="CREATE TABLE dwd.xxx (...);"></textarea></div>
      <div class="field"><label for="tableEtlInput">ETL SQL（可选）</label><textarea id="tableEtlInput" placeholder="INSERT INTO dwd.xxx SELECT ...;"></textarea></div>
      <div class="drawer-actions"><button class="btn" id="tablePreviewBtn">预览解析</button><button class="btn primary" id="tableImportRunBtn">确认导入</button></div>
      <div class="import-progress" id="tableImportStatus" role="status" aria-live="polite"></div>
      <div class="preview-shell" id="tablePreviewArea"><div class="load-state"><strong>尚未预览</strong>先粘贴 DDL，点击“预览解析”。</div></div>
    </div>
  </div></div>
  <div class="drawer-overlay" id="metadataPreviewDrawer" role="dialog" aria-modal="true" aria-labelledby="metadataPreviewTitle"><div class="drawer" style="width:min(880px,96vw)">
    <div class="drawer-shell">
      <button class="drawer-close" id="metadataPreviewClose" aria-label="关闭保存前预览">×</button>
      <div class="eyebrow">Metadata diff preview</div>
      <h2 id="metadataPreviewTitle">保存前变更预览</h2>
      <div class="subtle" id="metadataPreviewLead">保存前先检查表级与字段级元数据差异。</div>
      <div class="grid two" style="margin-top:12px">
        <div class="field"><label for="metadataRevisionSource">变更来源</label><input id="metadataRevisionSource" value="detail_editor" placeholder="例如：detail_editor / asset_bulk_edit"></div>
        <div class="field"><label for="metadataRevisionOperator">操作人</label><input id="metadataRevisionOperator" placeholder="例如：zhangsan"></div>
      </div>
      <div class="field"><label for="metadataRevisionReason">变更原因 / 备注</label><textarea id="metadataRevisionReason" placeholder="例如：补齐中文名、负责人和留存策略"></textarea></div>
      <div class="summary-grid" id="metadataPreviewSummary"></div>
      <div class="preview-shell" id="metadataPreviewBody"><div class="load-state"><strong>暂无变更</strong>当前没有待提交的元数据差异。</div></div>
      <div class="drawer-actions"><button class="btn" id="metadataPreviewCancel">取消</button><button class="btn primary" id="metadataPreviewConfirm">确认保存</button></div>
    </div>
  </div></div>
  <div class="toast" id="toast">操作已完成</div>`;
