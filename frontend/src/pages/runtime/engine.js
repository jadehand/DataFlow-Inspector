import { installAssistant } from "./assistant.js";
import { installCatalog } from "./catalog.js";
import { installCore } from "./core.js";
import { bindAssistantEvents } from "./events/assistant-events.js";
import { bindCatalogEvents } from "./events/catalog-events.js";
import { bindImpactEvents } from "./events/impact-events.js";
import { bindImportEvents } from "./events/import-events.js";
import { bindSessionEvents } from "./events/session-events.js";
import { installImpact } from "./impact.js";
import { installImports } from "./imports.js";
import { installSession } from "./session.js";

const installers = [
  installCore,
  installCatalog,
  installSession,
  installImports,
  installImpact,
  installAssistant
];

const eventBinders = [
  bindSessionEvents,
  bindImportEvents,
  bindCatalogEvents,
  bindImpactEvents,
  bindAssistantEvents
];

function createRuntimeState(store) {
  const route = store.getState();
  return {
    mode: "connecting",
    projectId: route.projectId || null,
    projects: [],
    versions: [],
    wizardStep: 1,
    preflight: null,
    importResult: null,
    tablePreview: null,
    selectedRelationIndex: null,
    selectedTableName: route.table || null,
    selectedTableDetail: null,
    detailDraft: null,
    compareResult: null,
    metadataCompareResult: null,
    selectedVersionMeta: {},
    selectedAssets: [],
    metadataRevisions: [],
    metadataPreviewResolver: null,
    metadataPreviewContext: null,
    impactSeed: null,
    routeLeftVersion: route.leftVersion || null,
    routeRightVersion: route.rightVersion || null,
    routeFocus: route.focus || null,
    importHistoryPollGeneration: 0
  };
}

function createScheduler() {
  const timers = new Set();
  return {
    defer(callback, delay) {
      const timer = setTimeout(() => {
        timers.delete(timer);
        callback();
      }, delay);
      timers.add(timer);
      return timer;
    },
    destroy() {
      timers.forEach(timer => clearTimeout(timer));
      timers.clear();
    }
  };
}

export function createFeatureEngine(runtime = {}) {
  const config = runtime.config || {};
  const apiRoot = config.apiRoot || "";
  const scheduler = createScheduler();
  const ctx = {
    $: id => document.getElementById(id),
    apiOrigin: config.apiOrigin || apiRoot.replace(/\/api\/?$/, ""),
    apiRoot,
    apis: runtime.apis,
    config,
    defer: scheduler.defer,
    params: new URLSearchParams(location.search),
    router: runtime.router,
    runtime,
    state: createRuntimeState(runtime.store),
    store: runtime.store,
    tableStrategyLabels: {
      check: "先预览并检测冲突",
      confirm_precise: "确认精确导入",
      merge_inferred: "确认推断关系并导入",
      accept_orphan: "作为孤立表导入",
      replace: "覆盖已有表定义",
      keep: "保留已有版本",
      merge: "合并字段与血缘"
    },
    ui: runtime.ui
  };

  installers.forEach(install => install(ctx));
  const cleanups = eventBinders.map(bind => bind(ctx));

  return () => {
    cleanups.reverse().forEach(cleanup => cleanup?.());
    scheduler.destroy();
  };
}
