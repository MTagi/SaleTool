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
  getRun: (runId) => request(`/api/search/runs/${runId}`),

  getSettings: () => request("/api/settings"),
  saveSettings: (settings) => request("/api/settings", { method: "PUT", body: settings }),
  testConnection: (target) => request("/api/settings/test", { method: "POST", body: { target } }),

  startEnrich: (targets) => request("/api/enrich", { method: "POST", body: { targets } }),
  getEnrichJob: (jobId) => request(`/api/enrich/jobs/${jobId}`),
  listEnrichJobs: () => request("/api/enrich/jobs"),
};
