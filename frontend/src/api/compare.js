export const createCompareApi = client => ({
  project: (projectId, left, right) => client.request(
    `/projects/${encodeURIComponent(projectId)}/compare?left=${encodeURIComponent(left)}&right=${encodeURIComponent(right)}`
  ),
  table: (projectId, table, left, right) => client.request(
    `/projects/${encodeURIComponent(projectId)}/tables/${encodeURIComponent(table)}/compare?left=${encodeURIComponent(left)}&right=${encodeURIComponent(right)}`
  ),
  metadata: (projectId, left, right) => client.request(
    `/projects/${encodeURIComponent(projectId)}/metadata/compare?left=${encodeURIComponent(left)}&right=${encodeURIComponent(right)}`
  )
});
