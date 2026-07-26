import { createAssistantPage } from "./assistant.js";
import { createAssetsPage } from "./assets.js";
import { createComparePage } from "./compare.js";
import { createDetailPage } from "./detail.js";
import { createImpactPage } from "./impact.js";
import { createImportsPage } from "./imports.js";
import { createLineagePage } from "./lineage.js";
import { createMetricsPage } from "./metrics.js";
import { createOverviewPage } from "./overview.js";
import { createWorkflowsPage } from "./workflows.js";

export function createPages() {
  return [
    createOverviewPage(), createAssetsPage(), createDetailPage(),
    createLineagePage(), createWorkflowsPage(), createMetricsPage(),
    createImportsPage(), createComparePage(), createImpactPage(),
    createAssistantPage()
  ];
}
