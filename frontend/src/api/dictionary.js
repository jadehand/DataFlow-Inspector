export const createDictionaryApi = client => ({
  preview: (projectId, payload) => client.request(
    `/projects/${encodeURIComponent(projectId)}/dictionary/bulk/preview`,
    { method: "POST", json: payload }
  ),
  save: (projectId, payload) => client.request(
    `/projects/${encodeURIComponent(projectId)}/dictionary/bulk`,
    { method: "PUT", json: payload }
  ),
  revisions: projectId => client.request(`/projects/${encodeURIComponent(projectId)}/metadata/revisions`),
  exportUrl: projectId => client.href(`/projects/${encodeURIComponent(projectId)}/dictionary/export`),
  exportFile: projectId => client.download(
    `/projects/${encodeURIComponent(projectId)}/dictionary/export`
  )
});
