import { createRuntimeConfig, createApiClient } from "./api/client.js";
import { createAssistantApi } from "./api/assistant.js";
import { createAssetsApi } from "./api/assets.js";
import { createCatalogApi } from "./api/catalog.js";
import { createCompareApi } from "./api/compare.js";
import { createDictionaryApi } from "./api/dictionary.js";
import { createDetailApi } from "./api/detail.js";
import { createImpactApi } from "./api/impact.js";
import { createImportsApi } from "./api/imports.js";
import { createLineageApi } from "./api/lineage.js";
import { createProjectsApi } from "./api/projects.js";
import { APP_SHELL } from "./components/app-shell.js";
import { createUiRuntime } from "./components/ui-runtime.js";
import { DATAFLOW_MOCK } from "./demo/mock-data.js";
import { createPages } from "./pages/index.js";
import { createRouter } from "./router.js";
import { createDemoStore } from "./state/demo-store.js";
import { createLiveStore } from "./state/live-store.js";
import { createInitialState, createStore } from "./state/store.js";
import { initProductApp } from "./product-app.js";

const root = document.getElementById("app");

if (!root) {
  throw new Error("Missing #app mount node");
}

const config = createRuntimeConfig(window.location);
const store = createStore(createInitialState());
const api = createApiClient(config);
const liveStore = createLiveStore();
const demoStore = createDemoStore(DATAFLOW_MOCK);
const router = createRouter({ store });

// Hydrate the route before any page or business runtime takes its initial snapshot.
router.start();

root.innerHTML = APP_SHELL;

const ui = createUiRuntime({
  store,
  router
});

const apis = {
  assistant: createAssistantApi(api),
  assets: createAssetsApi(api),
  catalog: createCatalogApi(api),
  compare: createCompareApi(api),
  dictionary: createDictionaryApi(api),
  detail: createDetailApi(api),
  impact: createImpactApi(api),
  imports: createImportsApi(api),
  lineage: createLineageApi(api),
  projects: createProjectsApi(api)
};
const context = {
  apis,
  config,
  demoStore,
  liveStore,
  router,
  store,
  ui
};

const pages = createPages();
pages.forEach(page => page.mount(context));

const cleanupShell = store.subscribe(state => {
  document.body.dataset.page = state.activePage;
  document.body.dataset.connectionMode = state.connectionMode;
  document.querySelectorAll(".page").forEach(node => {
    node.classList.toggle("active", node.id === `page-${state.activePage}`);
  });
  document.querySelectorAll(".nav button").forEach(node => {
    node.classList.toggle("active", node.dataset.page === state.activePage);
  });
});

const cleanupProductApp = initProductApp(context);

window.addEventListener("pagehide", () => {
  pages.forEach(page => page.unmount());
  cleanupProductApp?.();
  cleanupShell();
  ui.destroy?.();
  router.destroy();
}, { once: true });
