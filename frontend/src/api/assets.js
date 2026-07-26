export const createAssetsApi = client => ({
  list: projectId => client.request(
    `/projects/${encodeURIComponent(projectId)}/tables`
  ),
  previewImport: (projectId, body) => client.request(
    `/projects/${encodeURIComponent(projectId)}/tables/preview`,
    { method: "POST", body }
  ),
  importOne: (projectId, body) => client.request(
    `/projects/${encodeURIComponent(projectId)}/tables/import`,
    { method: "POST", body }
  )
});
