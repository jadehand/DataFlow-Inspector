export function createUiRuntime({ store, router }) {
const callbacks={assetSelect:null,nodeSelect:null,assetSelectionChange:null};
let demoTables = [];
let tables = [];
const selectedAssets = new Set();
const layerColor = {SOURCE:'var(--source)',ODS:'var(--ods)',DWD:'var(--dwd)',DWS:'var(--dws)',ADS:'var(--ads)',DIM:'#55718c'};
function updateAssetSelectionSummary(){
  const selectedCount = selectedAssets.size;
  document.getElementById('assetSelectionSummary').textContent = selectedCount ? `已选中 ${selectedCount} 个资产` : '未选中资产';
  const rows = tables.filter(t=>selectedAssets.has(t.name));
  const selectAll = document.getElementById('assetSelectAll');
  const visibleRows = tables.filter(t=>{
    const q=document.getElementById('assetSearch').value.toLowerCase(), layer=document.getElementById('layerFilter').value, flow=document.getElementById('assetFlowFilter').value, risk=document.getElementById('riskOnly').checked;
    const haystack=[t.name,t.desc,t.displayName,t.database,t.flow,t.partition,t.etl,t.owner,t.note].join(' ').toLowerCase();
    return (!q||haystack.includes(q))&&(!layer||t.layer===layer)&&(!flow||t.flow===flow)&&(!risk||t.risk);
  });
  selectAll.checked = !!visibleRows.length && visibleRows.every(t=>selectedAssets.has(t.name));
  selectAll.indeterminate = !!visibleRows.length && !selectAll.checked && visibleRows.some(t=>selectedAssets.has(t.name));
  callbacks.assetSelectionChange?.(rows.map(t=>({...t})));
}
function renderAssets(){
  const q=document.getElementById('assetSearch').value.toLowerCase(), layer=document.getElementById('layerFilter').value, flow=document.getElementById('assetFlowFilter').value, risk=document.getElementById('riskOnly').checked;
  const rows=tables.filter(t=>{
    const haystack=[t.name,t.desc,t.displayName,t.database,t.flow,t.partition,t.etl,t.owner,t.note].join(' ').toLowerCase();
    return (!q||haystack.includes(q))&&(!layer||t.layer===layer)&&(!flow||t.flow===flow)&&(!risk||t.risk);
  }).map(t=>`<tr data-table="${t.name}">
    <td class="selection-cell"><input type="checkbox" data-select-table="${t.name}" ${selectedAssets.has(t.name)?'checked':''} aria-label="选择 ${t.name}" /></td>
    <td><div class="table-name">${t.name}</div><div class="table-desc"><span class="tag" style="--tag:${layerColor[t.layer]||'#55718c'}">${t.layer}</span> ${t.flow?`<span class="tag" style="--tag:#d7e8ff;color:#245f9a">${t.flow}</span>`:''} ${t.displayName||t.desc||''}</div><div class="table-desc mono">${t.database||'—'}</div></td>
    <td><div>${t.partition||'—'}</div><div class="table-desc">${t.grain||'—'}</div></td>
    <td><div>${t.upstream||'—'}</div><div class="table-desc mono">${t.time||'—'}</div></td>
    <td><div class="mono">${t.etl||t.ddl||'—'}</div><div class="table-desc mono">${t.ddl||''}</div></td>
    <td><div>${t.owner||'待补充'}</div><div class="table-desc">${t.frequency||'频率待补充'} · ${t.retention||'留存待补充'}</div></td>
    <td><div>${t.fields||0} 字段</div><div class="table-desc">${t.relation||'—'}</div></td>
    <td>${t.risk?'<span class="tiny-risk"></span>待检查':'<span style="color:var(--success)">正常</span>'}<div class="table-desc">${t.note||''}</div>${t._draft?'<div class="draft-note">本页草稿已修改</div>':''}</td>
  </tr>`).join('');
  document.getElementById('assetRows').innerHTML=rows||`<tr><td colspan="8"><div class="empty-shell"><strong>${tables.length?'没有符合条件的数据资产':'尚未加载真实数据资产'}</strong>${tables.length?'请调整筛选条件。':'请先导入项目包，或手动切换到演示模式。'}</div></td></tr>`;
  document.querySelectorAll('#assetRows tr[data-table]').forEach(r=>r.onclick=e=>{if(e.target.closest('input[data-select-table]'))return;if(callbacks.assetSelect){callbacks.assetSelect(r.dataset.table)}else{navigate('detail')}});
  document.querySelectorAll('input[data-select-table]').forEach(box=>box.onchange=e=>{const name=e.target.dataset.selectTable;if(e.target.checked)selectedAssets.add(name);else selectedAssets.delete(name);updateAssetSelectionSummary()});
  updateAssetSelectionSummary();
}
const assetFilters=['assetSearch','layerFilter','assetFlowFilter','riskOnly'].map(id=>document.getElementById(id));
assetFilters.forEach(element=>element.addEventListener('input',renderAssets)); renderAssets();
document.getElementById('assetSelectAll').onchange=e=>{document.querySelectorAll('input[data-select-table]').forEach(box=>{box.checked=e.target.checked;const name=box.dataset.selectTable;if(e.target.checked)selectedAssets.add(name);else selectedAssets.delete(name)});updateAssetSelectionSummary()};
let demoMetrics = [];
function normalizeDemoMetric(metric) { return {
  name: metric.name || metric.display_name || '未命名指标',
  code: metric.code || metric.field_name || metric.name || '—',
  formula: metric.formula || metric.expression || '—',
  grain: metric.grain || metric.time_grain || '待识别',
  status: metric.status === 'warning' || metric.status === 'inferred' ? '待确认' : '已确认',
  consumers: Array.isArray(metric.consumers) ? metric.consumers.length : (metric.consumer_count ?? null)
}; }
let metrics=[];
function metricValue(metric,key,index){return Array.isArray(metric)?metric[index]:metric[key]}
function filteredMetrics(){const q=document.getElementById('metricSearch').value.toLowerCase();const grain=document.getElementById('metricGrainFilter').value;const status=document.getElementById('metricStatusFilter').value;return metrics.filter(metric=>{const name=metricValue(metric,'name',0)||'';const code=metricValue(metric,'code',1)||'';const metricGrain=metricValue(metric,'grain',3)||'';const metricStatus=metricValue(metric,'status',4)||'';return (!q||(name+code).toLowerCase().includes(q))&&(!grain||String(metricGrain).includes(grain))&&(!status||metricStatus===status)})}
function renderMetrics(){const list=filteredMetrics();document.getElementById('metricGrid').innerHTML=list.length?list.map(metric=>{const name=metricValue(metric,'name',0),code=metricValue(metric,'code',1),formula=metricValue(metric,'formula',2),grain=metricValue(metric,'grain',3),status=metricValue(metric,'status',4),consumers=metricValue(metric,'consumers',5);return `<div class="card metric-card"><div style="display:flex;justify-content:space-between"><div><h3>${name}</h3><div class="table-desc mono">${code}</div></div><span class="health ${status==='已确认'?'ok':'warn'}">${status}</span></div><div class="formula">${formula}</div><div class="metric-foot"><span>粒度：${grain}</span><span>${consumers==null?'消费方待识别':`${consumers} 个消费方`}</span></div></div>`}).join(''):`<div class="card"><div class="empty-shell"><strong>${metrics.length?'没有符合条件的指标':'尚未生成指标清单'}</strong>${metrics.length?'请调整筛选条件。':'完成真实分析后这里会展示指标口径。'}</div></div>`}
const metricFilters=['metricSearch','metricGrainFilter','metricStatusFilter'].map(id=>document.getElementById(id));
metricFilters.forEach(element=>element.addEventListener('input',renderMetrics));renderMetrics();
let demoNodes = [];
function normalizeDemoNode(table, index) { return {
  id: table.id || table.qualifiedName || table.name,
  x: 8 + ({SOURCE:0,RDS:0,ODS:1,DWD:2,DIM:2,DWS:3,ADS:4}[String(table.layer || 'OTHER').toUpperCase()] ?? 2) * 152,
  y: 45 + (index % 4) * 110,
  n: table.qualifiedName || table.name,
  l: String(table.layer || 'OTHER').toUpperCase(),
  d: table.description || table.desc || '演示数据资产'
}; }
let demoEdges = [];
function normalizeDemoEdge(edge) { return {
  source: edge.source,
  target: edge.target
}; }
let nodes=[];
let graphEdges=[];
function addEdge(area,a,b,hot=false,sourceId,targetId){const ax=a.x+120,ay=a.y+40,bx=b.x,by=b.y+40,dx=bx-ax,dy=by-ay,len=Math.sqrt(dx*dx+dy*dy),ang=Math.atan2(dy,dx)*180/Math.PI;const e=document.createElement('div');e.className='edge'+(hot?' hot':'');e.style.cssText=`left:${ax}px;top:${ay}px;width:${len}px;transform:rotate(${ang}deg)`;e.dataset.source=String(sourceId||a.id||a.n);e.dataset.target=String(targetId||b.id||b.n);area.appendChild(e)}
function focusGraphNode(nodeIdOrName){const key=String(nodeIdOrName||'');if(!key)return false;const nodeEls=[...document.querySelectorAll('#graphArea .node')];const edgeEls=[...document.querySelectorAll('#graphArea .edge')];const target=nodeEls.find(el=>el.dataset.nodeId===key||el.querySelector('strong')?.textContent===key);if(!target)return false;const normalized=target.dataset.nodeId;nodeEls.forEach(el=>el.classList.remove('selected','related','dimmed'));edgeEls.forEach(el=>el.classList.remove('related','dimmed'));nodeEls.forEach(el=>el.classList.add('dimmed'));edgeEls.forEach(el=>el.classList.add('dimmed'));target.classList.remove('dimmed');target.classList.add('selected','related');edgeEls.filter(el=>el.dataset.source===normalized||el.dataset.target===normalized).forEach(el=>{el.classList.remove('dimmed');el.classList.add('related')});nodeEls.filter(el=>edgeEls.some(edge=>(edge.dataset.source===normalized&&edge.dataset.target===el.dataset.nodeId)||(edge.dataset.target===normalized&&edge.dataset.source===el.dataset.nodeId))).forEach(el=>{el.classList.remove('dimmed');el.classList.add('related')});target.scrollIntoView({behavior:'smooth',block:'center',inline:'center'});return true}
function clearGraphFocus(){document.querySelectorAll('#graphArea .node').forEach(el=>el.classList.remove('selected','related','dimmed'));document.querySelectorAll('#graphArea .edge').forEach(el=>el.classList.remove('related','dimmed','hot'))}
function selectGraphNode(n,el){document.querySelectorAll('#graphArea .node').forEach(x=>x.classList.remove('selected'));el.classList.add('selected');document.getElementById('evidenceTitle').textContent=n.n;document.getElementById('evidenceDesc').textContent=n.d+'，当前节点已在血缘图中定位。';document.getElementById('evidenceGrain').textContent=n.grain||'—';document.getElementById('evidenceScript').textContent=n.script||'—';document.getElementById('evidenceRelation').textContent=n.relation||'—'}
function renderGraph(){const area=document.getElementById('graphArea');area.innerHTML='';if(!nodes.length){area.innerHTML='<div class="empty-shell" style="padding-top:140px"><strong>尚未生成血缘图</strong>完成真实分析后，这里会展示表级或字段级血缘。</div>';return}const query=document.getElementById('lineageSearch').value.trim().toLowerCase();const visibleNodes=query?nodes.filter(n=>`${n.n} ${n.d}`.toLowerCase().includes(query)):nodes;const visibleIds=new Set(visibleNodes.map(n=>String(n.id||n.n)));const byId=new Map(nodes.map((n,i)=>[String(n.id||n.n),i]));const pairs=graphEdges.map(e=>({sourceIndex:byId.get(String(e.source)),targetIndex:byId.get(String(e.target)),sourceId:String(e.source),targetId:String(e.target)})).filter(p=>p.sourceIndex!==undefined&&p.targetIndex!==undefined&&visibleIds.has(p.sourceId)&&visibleIds.has(p.targetId));pairs.forEach((p,i)=>addEdge(area,nodes[p.sourceIndex],nodes[p.targetIndex],i<6,p.sourceId,p.targetId));visibleNodes.forEach(n=>{const el=document.createElement('div');el.className='node';el.style.cssText=`left:${n.x}px;top:${n.y}px;--c:${layerColor[n.l]||'#55718c'}`;el.tabIndex=0;el.dataset.nodeId=String(n.id||n.n);el.setAttribute('role','button');el.setAttribute('aria-label',`${n.l} 表 ${n.n}，${n.d}`);el.innerHTML=`<span class="layer">${n.l}</span><strong>${n.n}</strong><small>${n.d}</small>`;el.onclick=()=>{selectGraphNode(n,el);callbacks.nodeSelect?.(String(n.id||n.n))};el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();el.click()}};area.appendChild(el)});if(query&&!visibleNodes.length)area.innerHTML='<div class="empty-shell" style="padding-top:140px"><strong>没有匹配的血缘节点</strong>请调整搜索条件。</div>'}renderGraph();
const lineageSearch=document.getElementById('lineageSearch');
lineageSearch.addEventListener('input',renderGraph);
function navigate(page,patch={}){document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));const target=document.getElementById('page-'+page);if(target)target.classList.add('active');document.querySelectorAll('.nav button').forEach(b=>b.classList.toggle('active',b.dataset.page===page));document.getElementById('sidebar').classList.remove('open');router.navigate(page,patch);window.scrollTo({top:0,behavior:'smooth'})}
document.querySelectorAll('[data-page],[data-goto]').forEach(el=>el.onclick=()=>navigate(el.dataset.page||el.dataset.goto));
document.querySelectorAll('.pipe-node').forEach(n=>n.onclick=()=>{navigate('assets');document.getElementById('layerFilter').value=n.dataset.layer==='SOURCE'?'':n.dataset.layer;renderAssets()});
document.getElementById('menuBtn').onclick=()=>document.getElementById('sidebar').classList.toggle('open');
const toast=document.getElementById('toast');let toastTimer=null;function showToast(t){toast.textContent=t;toast.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>{toastTimer=null;toast.classList.remove('show')},2200)}
const ui={navigate,renderAssets,renderMetrics,renderGraph,showToast,exportMetrics(){const rows=filteredMetrics();if(!rows.length)return showToast('当前没有可导出的指标');const csv=['name,code,formula,grain,status,consumers'].concat(rows.map(metric=>[metricValue(metric,'name',0),metricValue(metric,'code',1),metricValue(metric,'formula',2),metricValue(metric,'grain',3),metricValue(metric,'status',4),metricValue(metric,'consumers',5)??''].map(value=>`"${String(value??'').replaceAll('"','""')}"`).join(','))).join('\n');const blob=new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'});const href=URL.createObjectURL(blob);const link=document.createElement('a');link.href=href;link.download='dataflow-metrics.csv';link.click();URL.revokeObjectURL(href)},setTables(v){tables=v||[];selectedAssets.forEach(name=>{if(!tables.some(t=>t.name===name))selectedAssets.delete(name)})},setMetrics(v){metrics=v||[]},setNodes(v){nodes=v||[]},setEdges(v){graphEdges=v||[]},clearData(){demoTables=[];demoMetrics=[];demoNodes=[];demoEdges=[];tables=[];metrics=[];nodes=[];graphEdges=[];selectedAssets.clear();renderAssets();renderMetrics();renderGraph();updateAssetSelectionSummary();clearGraphFocus()},restoreDemo(demoData){demoTables=((demoData&&demoData.tables)||[]).slice();demoMetrics=((demoData&&demoData.metrics)||[]).map(normalizeDemoMetric);demoNodes=((demoData&&demoData.tables)||[]).map(normalizeDemoNode);demoEdges=((demoData&&demoData.lineage)||[]).map(normalizeDemoEdge);tables=demoTables.slice();metrics=demoMetrics.map(m=>({...m}));nodes=demoNodes.map(n=>({...n}));graphEdges=demoEdges.map(edge=>({...edge}));selectedAssets.clear();renderAssets();renderMetrics();renderGraph()},getTables(){return tables.map(t=>({...t}))},getSelectedTables(){return tables.filter(t=>selectedAssets.has(t.name)).map(t=>({...t}))},applyAssetDrafts(patch){if(!patch)return;const names=[...selectedAssets];tables=tables.map(t=>names.includes(t.name)?{...t,...patch,_draft:true}:t);renderAssets()},focusNode:focusGraphNode,clearGraphFocus,highlightMainPath(){clearGraphFocus();document.querySelectorAll('#graphArea .edge').forEach((edge,index)=>edge.classList.toggle('hot',index<6));document.getElementById('lineageFocusHint').textContent=graphEdges.length?'已高亮当前主链路':'当前没有可高亮的血缘关系'},focusHint(text){const el=document.getElementById('lineageFocusHint');if(el)el.textContent=text||'尚未指定聚焦对象'},setCallbacks(next){Object.assign(callbacks,next||{})},destroy(){assetFilters.forEach(element=>element.removeEventListener('input',renderAssets));metricFilters.forEach(element=>element.removeEventListener('input',renderMetrics));lineageSearch.removeEventListener('input',renderGraph);clearTimeout(toastTimer);toastTimer=null;Object.assign(callbacks,{assetSelect:null,nodeSelect:null,assetSelectionChange:null})}};
  return ui;
}
