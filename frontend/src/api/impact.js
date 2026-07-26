export const createImpactApi = client => ({
  analyze: (projectId, payload) => client.request(
    `/projects/${encodeURIComponent(projectId)}/impact-analysis`,
    { method: "POST", json: payload }
  )
});
