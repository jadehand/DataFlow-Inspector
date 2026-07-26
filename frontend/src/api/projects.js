export const createProjectsApi = client => ({
  list: () => client.request("/projects"),
  create: payload => client.request("/projects", {
    method: "POST", json: payload
  })
});
