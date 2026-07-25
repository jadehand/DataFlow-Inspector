# DataFlow Inspector 前端

这是一个无构建依赖的单文件产品前端，保留九个业务页面，并支持连接 DataFlow Inspector API。

## 运行

不要直接双击 HTML（浏览器可能限制跨域请求），请从 `src/` 启动静态服务器：

```bash
python3 -m http.server 15173 --directory src
```

访问：

```text
http://127.0.0.1:15173/
```

默认请求同源 `/api`。本地后端运行在 `18080` 时，可以显式覆盖：

```text
http://127.0.0.1:15173/?api=http://127.0.0.1:18080/api
```

跨端口运行时，后端需要允许前端来源 `http://127.0.0.1:15173` 的 CORS 请求。

## 数据模式

- `真实数据`：项目、资产、血缘、指标、影响分析、版本比较和问答均请求后端。
- `连接失败`：不会自动把 Mock 数据冒充真实结果；页面会显示错误。
- `演示数据`：只能由用户点击“显式切换演示模式”进入，上传不会发送或保存。

## 导入协议

前端以原始 ZIP 二进制上传：

```http
POST /api/projects/{project_id}/imports?filename=project.zip&note=...
Content-Type: application/zip
```

项目包可包含 DDL、加工 SQL、`manifest.yaml`、`metadata/jobs.csv` 和脱敏样例。

## 文件

- `src/index.html`：九页面应用及设计样式。
- `src/product-app.js`：API 客户端、数据模式与业务交互。
- `src/mock-data.js`：用户显式进入演示模式后使用的样例数据。
