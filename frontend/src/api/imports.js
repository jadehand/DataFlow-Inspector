export const createImportsApi = client => ({
  list: projectId => client.request(`/projects/${encodeURIComponent(projectId)}/imports`),
  get: importId => client.request(`/imports/${encodeURIComponent(importId)}`),
  preflight: file => client.request("/imports/preflight", {
    method: "POST", body: file, headers: { "Content-Type": "application/zip" }
  }),
  upload: (projectId, file, note = "") => client.request(
    `/projects/${encodeURIComponent(projectId)}/imports?filename=${encodeURIComponent(file.name)}&note=${encodeURIComponent(note)}`,
    { method: "POST", body: file, headers: { "Content-Type": "application/zip" } }
  ),
  previewTable: (projectId, body) => client.request(
    `/projects/${encodeURIComponent(projectId)}/tables/preview`,
    { method: "POST", body }
  ),
  importTable: (projectId, body) => client.request(
    `/projects/${encodeURIComponent(projectId)}/tables/import`,
    { method: "POST", body }
  ),
  templateUrl: kind => client.href(`/templates/${encodeURIComponent(kind)}`)
});

export async function waitForImport(importsApi, importId, {
  attempts = 120, intervalMs = 1000, onProgress
} = {}) {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const result = await importsApi.get(importId);
    onProgress?.(result, attempt);
    const status = String(result?.status || "").toLowerCase();
    if (status === "completed") return result;
    if (status === "failed") throw new Error(result?.error || result?.detail || "导入分析失败");
    await new Promise(resolve => setTimeout(resolve, intervalMs));
  }
  throw new Error("导入分析等待超时，请稍后在导入历史中查看状态");
}
