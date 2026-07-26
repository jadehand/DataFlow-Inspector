export const createLineageApi = client => ({
  get: (projectId, params = {}) => {
    const query = new URLSearchParams(params);
    return client.request(`/projects/${encodeURIComponent(projectId)}/lineage?${query}`);
  },
  impact: (projectId, payload) => client.request(
    `/projects/${encodeURIComponent(projectId)}/impact-analysis`,
    { method: "POST", json: payload }
  )
});
