# DataFlow Inspector 前端

这是一个无构建依赖的模块化产品前端，保留现有业务页面与 DOM/CSS，并支持连接 DataFlow Inspector API。

## 运行

不要直接双击 HTML（浏览器可能限制跨域请求），请从 `src/` 启动静态服务器：

```bash
python3 -m http.server 15173 --directory src
```

访问：

```text
http://127.0.0.1:15173/
```

如果和后端一起联调，优先从仓库根目录执行：

```bash
make dev
```

该脚本固定使用 `15173` / `18080`，并显式拒绝占用 `8080`。

默认请求同源 `/api`。本地后端运行在 `18080` 时，可以显式覆盖：

```text
http://127.0.0.1:15173/?api=http://127.0.0.1:18080/api
```

跨端口运行时，后端需要允许前端来源 `http://127.0.0.1:15173` 的 CORS 请求。

## 数据模式

- `真实数据`：项目、资产、血缘、指标、影响分析、版本比较和问答均请求后端。
- `真实数据` 下，表详情与批量编辑的元数据保存会先展示结构化差异预览，再确认写入。
- `连接失败`：不会自动把 Mock 数据冒充真实结果；页面会显示错误。
- `演示数据`：只能由用户点击“显式切换演示模式”进入，上传不会发送或保存。

## 版本与 Revision

前端当前同时展示两类“版本”：

- 导入分析版本：来自 `imports`
- 元数据修订版本：来自 `metadata revisions`

已接通的真实链路：

- 表详情页显示当前 metadata revision
- 保存前差异预览抽屉显示当前 revision 与即将生成的下一条 revision
- 版本比较页显示最近两次 metadata revision 的差异摘要
- metadata revision 显示来源、操作人和原因
- 版本比较页可直接把 compare / metadata revision diff 证据带入影响分析
- 表详情页可直接查看或导出该表对应的 DDL / ETL 原始文件

## 导入协议

前端以原始 ZIP 二进制上传：

```http
POST /api/projects/{project_id}/imports?filename=project.zip&note=...
Content-Type: application/zip
```

项目包可包含 DDL、加工 SQL、`manifest.yaml`、`metadata/jobs.csv` 和脱敏样例。

## 文件

- `src/index.html`：应用挂载点及设计样式。
- `src/app.js`：依赖组合根，负责创建 API、store、router、UI 和页面控制器。
- `src/product-app.js`：兼容应用启动协议的薄装配层。
- `src/api/*.js`：按 projects、assets、detail、imports、catalog、lineage、compare、impact、dictionary、assistant 划分的领域 API；网络请求仅允许出现在 `api/client.js`。
- `src/state/store.js`：统一的深层不可变导航/会话状态；项目切换会原子清理表、比较版本、聚焦对象和页面派生选择。
- `src/state/live-store.js`：真实接口数据快照，不读取演示数据。
- `src/state/demo-store.js`：演示快照，每次读取和重置均复制，避免与真实状态共享可变对象。
- `src/router.js`：管理 `page/project/table/left/right/focus` URL 状态，支持刷新恢复、`pushState` 和 `popstate`。
- `src/pages/*.js`：页面生命周期 adapter，只同步路由可观察状态并负责 cleanup，不重复绑定业务事件。
- `src/pages/application-controller.js`：应用生命周期组合层，不承载页面业务。
- `src/pages/runtime/*.js`：按 core、catalog、session、imports、impact、assistant 划分的领域深模块。
- `src/pages/runtime/events/*.js`：按领域唯一拥有 DOM 业务事件；每组事件使用独立 EventScope 并提供统一 cleanup。
- `src/pages/runtime/engine.js`：只安装领域能力、绑定事件组并统一销毁，不承载具体业务交互。
- `src/demo/mock-data.js`：仅在用户显式进入演示模式后使用的只读种子数据。

## 路由

页面状态使用 query 参数编码，例如：

```text
/?page=detail&project=12&table=dws.orders
/?page=compare&project=12&left=3&right=4
/?page=lineage&project=12&focus=dws.orders
```

页面导航写入浏览器历史，前进/后退由 `popstate` 恢复。业务模块之间通过 `app.js` 创建的显式 context 传递依赖，不使用 `window.DFI_UI` 或 document 自定义事件。

## P1 架构约束

- 页面生命周期 adapter 不发业务请求；运行时深模块只能依赖 `context.apis` 中的领域接口，不得使用通用 client。
- 同一 DOM 业务事件只能由一个运行时模块拥有，禁止页面 adapter 叠加旁路请求。
- `runtime/engine.js` 必须保持薄装配层，禁止直接出现 DOM 业务事件绑定。
- `pages/` 下所有业务模块递归限制在 500 行以内，静态 import 图不得出现循环依赖。
- 真实数据与演示数据使用不同 store；演示种子仅在用户显式切换后注入 UI。
- URL 是 `page/project/table/left/right/focus` 的可恢复状态来源。
- 所有订阅、回调和应用控制器必须返回 cleanup。
- 项目加载使用 request generation，迟到的旧项目响应不得覆盖当前项目。

## P2 真实功能闭环

- 从演示模式切回连接中、真实模式或错误态时，资产、指标、血缘、边和勾选状态会原子清空，真实错误页不会残留演示结果。
- 应用启动前先读取 `page/project/table/left/right/focus`，详情、比较和血缘深链支持直接打开与刷新恢复。
- 导入历史是独立页面，展示真实版本状态、分析摘要、错误与文件数；`queued/running/pending` 任务会继续轮询，用户也可手动刷新。
- 影响分析区域默认保持未分析状态，演示模式不会展示固定结果；只有真实后端响应才能打开结果区域。
- 比较与影响渲染兼容当前后端和增强返回结构，无版本或无建议时展示明确空态。
- 血缘支持层级/深度请求、节点搜索、聚焦与主链高亮；指标支持名称、粒度、状态筛选和当前结果 CSV 导出。
