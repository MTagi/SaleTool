const TOKEN_KEY = "saletool_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

async function request(path, { method = "GET", body, isForm = false } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (body && !isForm) headers["Content-Type"] = "application/json";

  const res = await fetch(path, {
    method,
    headers,
    body: body ? (isForm ? body : JSON.stringify(body)) : undefined,
  });

  const contentType = res.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");
  const data = isJson ? await res.json().catch(() => null) : null;

  if (!res.ok) {
    throw new Error(data?.detail || `Error ${res.status}`);
  }

  return data;
}

export const api = {
  login: (username, password) => request("/api/auth/login", { method: "POST", body: { username, password } }),
  me: () => request("/api/auth/me"),
  changePassword: (currentPassword, newPassword) =>
    request("/api/auth/change-password", {
      method: "POST",
      body: { current_password: currentPassword, new_password: newPassword },
    }),
  search: (formData) => request("/api/search", { method: "POST", body: formData, isForm: true }),
  listRuns: () => request("/api/search/runs"),
  getSearchOptions: () => request("/api/search/options"),
  getRun: (runId) => request(`/api/search/runs/${runId}`),

  getSettings: () => request("/api/settings"),
  saveSettings: (settings) => request("/api/settings", { method: "PUT", body: settings }),
  testConnection: (target) => request("/api/settings/test", { method: "POST", body: { target } }),

  startEnrich: (targets) => request("/api/enrich", { method: "POST", body: { targets } }),
  getEnrichJob: (jobId) => request(`/api/enrich/jobs/${jobId}`),

  listServices: () => request("/api/catalog"),
  createService: (service) => request("/api/catalog", { method: "POST", body: service }),
  updateService: (serviceId, service) =>
    request(`/api/catalog/${serviceId}`, { method: "PUT", body: service }),
  deleteService: (serviceId) => request(`/api/catalog/${serviceId}`, { method: "DELETE" }),

  startMatch: (runId, serviceIds, objective) =>
    request("/api/match", {
      method: "POST",
      body: { run_id: runId, service_ids: serviceIds, objective: objective || null },
    }),
  getMatchJob: (jobId) => request(`/api/match/jobs/${jobId}`),
  listMatchJobs: () => request("/api/match/jobs"),

  getStatus: () => request("/api/status"),

  getMessageOptions: () => request("/api/messages/options"),
  startMessages: (payload) => request("/api/messages", { method: "POST", body: payload }),
  getMessageJob: (jobId) => request(`/api/messages/jobs/${jobId}`),
};
