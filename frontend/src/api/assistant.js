export const createAssistantApi = client => ({
  ask: (projectId, question) => client.request(
    `/projects/${encodeURIComponent(projectId)}/assistant/query`,
    { method: "POST", json: { question } }
  )
});
