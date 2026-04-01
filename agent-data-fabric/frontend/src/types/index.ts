export interface User {
  id: string;
  email: string;
  full_name: string | null;
  role_name: string | null;
  is_active: boolean;
  created_at: string;
}

export interface Connector {
  id: string;
  name: string;
  connector_type: string;
  description: string | null;
  config: Record<string, any>;
  sync_mode: string;
  is_active: boolean;
  last_synced_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface MCPServer {
  id: string;
  name: string;
  image: string | null;
  container_id: string | null;
  sse_url: string | null;
  status: string;
  config: Record<string, any>;
  is_enabled: boolean;
  tool_count: number;
  created_at: string;
}

export interface MCPResource {
  id: string;
  uri: string;
  name: string;
  description: string | null;
  resource_type: string;
  source_type: string;
  mime_type: string | null;
  schema_json: Record<string, any> | null;
  last_updated: string;
}

export interface MCPTool {
  id: string;
  name: string;
  description: string | null;
  input_schema: Record<string, any>;
  source_type: string;
  server_name: string | null;
  is_active: boolean;
  created_at: string;
}

export interface MCPPrompt {
  id: string;
  name: string;
  description: string | null;
  template: string;
  variables: string[];
  created_at: string;
}

export interface CustomTool {
  id: string;
  name: string;
  description: string | null;
  code: string;
  input_schema: Record<string, any>;
  current_version: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Conversation {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: string;
  content: string;
  metadata: Record<string, any> | null;
  created_at: string;
}

export interface TraceEvent {
  type: string;
  agent?: string;
  tool?: string;
  status: string;
  payload?: Record<string, any>;
  sequence: number;
  duration_ms?: number;
}

export interface ObservabilitySummary {
  tokens_total: number;
  tokens_input: number;
  tokens_output: number;
  tokens_cache: number;
  avg_latency_ms: number;
  total_calls: number;
  top_models: { model: string; count: number }[];
}

export interface LLMCall {
  id: string;
  message_id: string | null;
  model: string;
  tokens_input: number;
  tokens_output: number;
  tokens_cache: number;
  latency_ms: number;
  tool_calls: any[] | null;
  created_at: string;
}

export interface SQLResult {
  columns: string[];
  rows: any[][];
  total: number;
  page: number;
  page_size: number;
  latency_ms: number;
}

export interface Capabilities {
  connectors: { id: string; name: string; type: string; description: string | null }[];
  mcp_tools: { id: string; name: string; description: string | null; source: string }[];
  custom_tools: { id: string; name: string; description: string | null }[];
  prompts: { id: string; name: string; description: string | null }[];
}
