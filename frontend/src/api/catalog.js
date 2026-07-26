export const createCatalogApi = client => ({
  catalog: projectId => client.request(`/projects/${encodeURIComponent(projectId)}/catalog`),
  tables: projectId => client.request(`/projects/${encodeURIComponent(projectId)}/tables`),
  tableDetail: (projectId, table) => client.request(
    `/projects/${encodeURIComponent(projectId)}/tables/${encodeURIComponent(table)}/detail`
  ),
  workflows: projectId => client.request(`/projects/${encodeURIComponent(projectId)}/workflows`),
  metrics: projectId => client.request(`/projects/${encodeURIComponent(projectId)}/metrics`),
  findings: projectId => client.request(`/projects/${encodeURIComponent(projectId)}/quality-findings`)
});
