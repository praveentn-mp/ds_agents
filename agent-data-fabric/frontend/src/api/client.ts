import axios from 'axios';

const API_BASE = '/api';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

// Attach auth token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('adf_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 — redirect to login
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('adf_token');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(err);
  }
);

export default api;

// ─── Auth ────────────────────────────────────────────────────────────────────
export const authApi = {
  login: (email: string, password: string) =>
    api.post('/auth/login', { email, password }),
  register: (email: string, password: string, full_name: string) =>
    api.post('/auth/register', { email, password, full_name }),
  me: () => api.get('/auth/me'),
  refresh: (refresh_token: string) =>
    api.post('/auth/refresh', { refresh_token }),
};

// ─── Connectors ──────────────────────────────────────────────────────────────
export const connectorApi = {
  list: () => api.get('/connectors'),
  create: (data: any) => api.post('/connectors', data),
  get: (id: string) => api.get(`/connectors/${id}`),
  update: (id: string, data: any) => api.put(`/connectors/${id}`, data),
  delete: (id: string) => api.delete(`/connectors/${id}`),
  test: (id: string) => api.post(`/connectors/${id}/test`),
  discoverSchema: (id: string) => api.post(`/connectors/${id}/discover-schema`),
  ingestStatus: (id: string) => api.get(`/connectors/${id}/ingest/status`),
  dataSummary: (id: string) => api.get(`/connectors/${id}/data-summary`),
};

// ─── MCP ─────────────────────────────────────────────────────────────────────
export const mcpApi = {
  listServers: () => api.get('/mcp/servers'),
  createServer: (data: any) => api.post('/mcp/servers', data),
  startServer: (id: string) => api.post(`/mcp/servers/${id}/start`),
  stopServer: (id: string) => api.post(`/mcp/servers/${id}/stop`),
  listResources: () => api.get('/mcp/registry/resources'),
  listTools: () => api.get('/mcp/registry/tools'),
  listPrompts: () => api.get('/mcp/registry/prompts'),
  renderPrompt: (name: string, variables: Record<string, string>) =>
    api.post('/mcp/registry/prompts/render', { prompt_name: name, variables }),
  dryRun: (tool_name: string, args: Record<string, any>) =>
    api.post('/mcp/registry/tools/dry-run', { tool_name, arguments: args }),
};

// ─── Tools ───────────────────────────────────────────────────────────────────
export const toolApi = {
  list: () => api.get('/tools'),
  create: (data: any) => api.post('/tools', data),
  get: (id: string) => api.get(`/tools/${id}`),
  update: (id: string, data: any) => api.put(`/tools/${id}`, data),
  execute: (id: string, args: Record<string, any>) =>
    api.post(`/tools/${id}/execute`, { arguments: args }),
  versions: (id: string) => api.get(`/tools/${id}/versions`),
};

// ─── Chat ────────────────────────────────────────────────────────────────────
export const chatApi = {
  conversations: () => api.get('/chat/conversations'),
  messages: (id: string) => api.get(`/chat/conversations/${id}/messages`),
};

// ─── SQL ─────────────────────────────────────────────────────────────────────
export const sqlApi = {
  execute: (data: { query: string; connector_id: string; page?: number; page_size?: number }) =>
    api.post('/sql/execute', data),
  history: () => api.get('/sql/history'),
  schema: (connectorId: string) => api.get(`/sql/schema/${connectorId}`),
};

// ─── Observability ───────────────────────────────────────────────────────────
export const observabilityApi = {
  summary: () => api.get('/observability/summary'),
  llmCalls: (page = 1, page_size = 50) =>
    api.get('/observability/llm-calls', { params: { page, page_size } }),
  traces: (messageId: string) => api.get(`/observability/traces/${messageId}`),
};

// ─── Capabilities ────────────────────────────────────────────────────────────
export const capabilitiesApi = {
  list: () => api.get('/capabilities'),
};

// ─── Health ──────────────────────────────────────────────────────────────────
export const healthApi = {
  check: () => api.get('/health'),
};
