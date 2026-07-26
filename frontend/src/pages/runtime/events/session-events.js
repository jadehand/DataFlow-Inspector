import { createEventScope } from "./event-scope.js";

export function bindSessionEvents(ctx) {
  const { state, $, ui, store, runtime } = ctx;
  const scope = createEventScope();
  let focusFrame = null;

  $("apiEndpoint").textContent = ctx.apiRoot;
  scope.assign($("retryConnection"), "onclick", ctx.loadProjects);
  scope.assign($("demoModeBtn"), "onclick", () => {
    ctx.setMode("demo");
    ui.restoreDemo(runtime.demoStore.reset());
    ctx.renderDemoContent();
    $("projectSelect").innerHTML = "<option>Token 请求流量（内置演示）</option>";
    ui.showToast("已显式切换到演示模式");
  });
  scope.assign($("refreshBtn"), "onclick", () => (
    state.mode === "live" ? ctx.loadProjectData() : ctx.loadProjects()
  ));
  scope.assign($("projectSelect"), "onchange", event => {
    ctx.switchProject(event.target.value);
  });

  const unsubscribeRoute = store.subscribe((next, previous) => {
    if (next.projectId !== previous.projectId) {
      state.projectId = next.projectId;
      ctx.clearProjectDerivedState();
      if ($("projectSelect")) $("projectSelect").value = next.projectId || "";
      if (state.mode === "live" && next.projectId) ctx.loadProjectData();
    }
    if (next.table !== previous.table && next.table) {
      state.selectedTableName = next.table;
      if (state.mode === "live") {
        ctx.loadTableDetail(next.table).catch(error => ui.showToast(error.message));
      }
    }
    if (next.leftVersion !== previous.leftVersion && $("compareLeft")) {
      state.routeLeftVersion = next.leftVersion;
      $("compareLeft").value = next.leftVersion || "";
    }
    if (next.rightVersion !== previous.rightVersion && $("compareRight")) {
      state.routeRightVersion = next.rightVersion;
      $("compareRight").value = next.rightVersion || "";
    }
    if (next.focus !== previous.focus && next.focus) {
      state.routeFocus = next.focus;
      if (focusFrame != null) cancelAnimationFrame(focusFrame);
      focusFrame = requestAnimationFrame(() => {
        focusFrame = null;
        const focused = ui.focusNode(next.focus);
        ui.focusHint(focused ? `已聚焦 ${next.focus}` : `未在当前血缘图中定位到 ${next.focus}`);
      });
    }
  });

  ctx.loadProjects();
  return () => {
    unsubscribeRoute();
    if (focusFrame != null) cancelAnimationFrame(focusFrame);
    scope.cleanup();
  };
}
