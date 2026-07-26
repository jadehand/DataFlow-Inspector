export const createDetailApi = client => ({
  get: (projectId, table) => client.request(
    `/projects/${encodeURIComponent(projectId)}/tables/${encodeURIComponent(table)}/detail`
  ),
  compare: (projectId, table, left, right) => client.request(
    `/projects/${encodeURIComponent(projectId)}/tables/${encodeURIComponent(table)}/compare?left=${encodeURIComponent(left)}&right=${encodeURIComponent(right)}`
  )
});
