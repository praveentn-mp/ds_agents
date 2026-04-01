-- =============================================================================
-- Agent Data Fabric — Database Initialization
-- =============================================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- =============================================================================
-- RBAC
-- =============================================================================

CREATE TABLE IF NOT EXISTS roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    permissions JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    full_name TEXT,
    role_id UUID REFERENCES roles(id),
    is_active BOOLEAN NOT NULL DEFAULT true,
    last_login TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked BOOLEAN NOT NULL DEFAULT false
);

-- =============================================================================
-- Connectors
-- =============================================================================

CREATE TABLE IF NOT EXISTS connectors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    connector_type TEXT NOT NULL,
    description TEXT,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    encrypted_credentials TEXT,
    sync_mode TEXT NOT NULL DEFAULT 'live',
    sync_interval_seconds INT DEFAULT 3600,
    last_synced_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT true,
    owner_id UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS connector_schemas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_id UUID NOT NULL REFERENCES connectors(id) ON DELETE CASCADE,
    version INT NOT NULL DEFAULT 1,
    schema_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_current BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS connector_perms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_id UUID NOT NULL REFERENCES connectors(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    role_id UUID REFERENCES roles(id),
    can_read BOOLEAN NOT NULL DEFAULT true,
    can_write BOOLEAN NOT NULL DEFAULT false,
    can_admin BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS sync_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_id UUID NOT NULL REFERENCES connectors(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending',
    rows_synced INT DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

-- =============================================================================
-- MCP Layer
-- =============================================================================

CREATE TABLE IF NOT EXISTS mcp_servers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    image TEXT,
    container_id TEXT,
    sse_url TEXT,
    status TEXT NOT NULL DEFAULT 'stopped',
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    encrypted_config TEXT,
    auto_register BOOLEAN NOT NULL DEFAULT true,
    is_enabled BOOLEAN NOT NULL DEFAULT true,
    registered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mcp_resources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uri TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    resource_type TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id UUID,
    mime_type TEXT,
    schema_json JSONB,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mcp_tools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT,
    input_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_type TEXT NOT NULL,
    source_id UUID,
    server_name TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mcp_prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    template TEXT NOT NULL,
    variables JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- Custom Tools
-- =============================================================================

CREATE TABLE IF NOT EXISTS custom_tools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    code TEXT NOT NULL,
    input_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    current_version INT NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT true,
    owner_id UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tool_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_id UUID NOT NULL REFERENCES custom_tools(id) ON DELETE CASCADE,
    version INT NOT NULL,
    code TEXT NOT NULL,
    input_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tool_perms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_id UUID NOT NULL REFERENCES custom_tools(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    role_id UUID REFERENCES roles(id),
    can_execute BOOLEAN NOT NULL DEFAULT true,
    can_edit BOOLEAN NOT NULL DEFAULT false
);

-- =============================================================================
-- Conversations & Observability
-- =============================================================================

CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    title TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS execution_traces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID REFERENCES messages(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    trace_type TEXT NOT NULL,
    agent_name TEXT,
    tool_name TEXT,
    payload JSONB,
    status TEXT NOT NULL DEFAULT 'running',
    duration_ms INT,
    sequence INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS llm_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID REFERENCES messages(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    model TEXT NOT NULL,
    tokens_input INT NOT NULL DEFAULT 0,
    tokens_output INT NOT NULL DEFAULT 0,
    tokens_cache INT NOT NULL DEFAULT 0,
    latency_ms INT NOT NULL DEFAULT 0,
    tool_calls JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sql_query_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    connector_id UUID REFERENCES connectors(id),
    query TEXT NOT NULL,
    row_count INT,
    duration_ms INT,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- RAG
-- =============================================================================

CREATE TABLE IF NOT EXISTS rag_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_uri TEXT NOT NULL,
    title TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rag_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES rag_documents(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- Indexes
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_traces_message ON execution_traces(message_id);
CREATE INDEX IF NOT EXISTS idx_traces_conversation ON execution_traces(conversation_id);
CREATE INDEX IF NOT EXISTS idx_llm_calls_conversation ON llm_calls(conversation_id);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_embedding ON rag_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_connectors_type ON connectors(connector_type);
CREATE INDEX IF NOT EXISTS idx_mcp_resources_uri ON mcp_resources USING gin (uri gin_trgm_ops);

-- =============================================================================
-- Seed RBAC Roles
-- =============================================================================

INSERT INTO roles (name, permissions) VALUES
    ('admin', '["manage_users","manage_connectors","manage_mcp_servers","manage_tools","build_tools","execute_sql_write","execute_sql_read","query_data","view_traces"]'),
    ('developer', '["manage_connectors","manage_mcp_servers","manage_tools","build_tools","execute_sql_write","execute_sql_read","query_data","view_traces"]'),
    ('analyst', '["execute_sql_read","query_data","view_traces"]'),
    ('viewer', '["query_data"]')
ON CONFLICT (name) DO NOTHING;

-- Seed admin user (password: admin123 — change immediately)
INSERT INTO users (email, hashed_password, full_name, role_id, is_active)
SELECT 'admin@adf.local',
       '$2b$12$psTHMlAXiKZnaK/B5XQ38.rP6fsw9jV1N5TcJre2Co.jYkoX2YGFa',
       'Admin User',
       r.id,
       true
FROM roles r WHERE r.name = 'admin'
ON CONFLICT (email) DO NOTHING;

-- =============================================================================
-- Seed MCP Prompts
-- =============================================================================

INSERT INTO mcp_prompts (name, description, template, variables) VALUES
    ('tool_selector', 'Given intent and available tools, pick the best tool(s)',
     'You are a tool selection expert. Given the user intent: {{intent}}\n\nAvailable tools:\n{{tools}}\n\nSelect the best tool(s) to satisfy this request. Return a JSON array of tool names with reasoning.',
     '["intent", "tools"]'),
    ('connector_vs_tool_decider', 'Decide between data path (connector) vs capability path (MCP tool)',
     'Given the user request: {{request}}\n\nAvailable connectors:\n{{connectors}}\n\nAvailable MCP tools:\n{{tools}}\n\nDecide: should this be handled via a data connector query, an MCP tool call, or a hybrid approach? Respond with: {"path": "connector|tool|hybrid", "reasoning": "..."}',
     '["request", "connectors", "tools"]'),
    ('query_planner', 'Decompose multi-step data question into execution plan',
     'You are a query planning expert. Decompose the following question into executable steps:\n\nQuestion: {{question}}\n\nAvailable resources:\n{{resources}}\n\nReturn a JSON array of steps, each with: {"step": N, "action": "query|tool_call|aggregate", "resource": "...", "details": "..."}',
     '["question", "resources"]'),
    ('mcp_server_selector', 'Given a task, pick the best Docker MCP server',
     'Given the task: {{task}}\n\nAvailable MCP servers:\n{{servers}}\n\nSelect the best server(s) to handle this task. Return: {"server": "...", "tool": "...", "reasoning": "..."}',
     '["task", "servers"]')
ON CONFLICT (name) DO NOTHING;

-- =============================================================================
-- Seed Default Custom Tools
-- =============================================================================

INSERT INTO custom_tools (name, description, code, input_schema) VALUES
    ('calculate_ltv',
     'Calculate Customer Lifetime Value from average revenue and churn rate',
     E'avg_revenue = arguments.get("avg_monthly_revenue", 0)\nchurn = arguments.get("monthly_churn_rate", 0.05)\nif churn <= 0:\n    result = {"error": "Churn rate must be > 0"}\nelse:\n    ltv = avg_revenue / churn\n    result = {"ltv": round(ltv, 2), "avg_monthly_revenue": avg_revenue, "monthly_churn_rate": churn}',
     '{"type": "object", "properties": {"avg_monthly_revenue": {"type": "number", "description": "Average monthly revenue per customer"}, "monthly_churn_rate": {"type": "number", "description": "Monthly churn rate (0-1)"}}, "required": ["avg_monthly_revenue", "monthly_churn_rate"]}'::jsonb),
    ('revenue_summary',
     'Summarize revenue by grouping — returns total, average, min, max from a list of amounts',
     E'amounts = arguments.get("amounts", [])\nif not amounts:\n    result = {"error": "No amounts provided"}\nelse:\n    result = {"total": round(sum(amounts), 2), "average": round(sum(amounts)/len(amounts), 2), "min": min(amounts), "max": max(amounts), "count": len(amounts)}',
     '{"type": "object", "properties": {"amounts": {"type": "array", "items": {"type": "number"}, "description": "List of revenue amounts"}}, "required": ["amounts"]}'::jsonb),
    ('deal_win_rate',
     'Calculate deal win rate from won and total deal counts',
     E'won = arguments.get("won_deals", 0)\ntotal = arguments.get("total_deals", 0)\nif total <= 0:\n    result = {"error": "total_deals must be > 0"}\nelse:\n    rate = won / total * 100\n    result = {"win_rate_pct": round(rate, 2), "won_deals": won, "total_deals": total}',
     '{"type": "object", "properties": {"won_deals": {"type": "integer", "description": "Number of won deals"}, "total_deals": {"type": "integer", "description": "Total number of deals"}}, "required": ["won_deals", "total_deals"]}'::jsonb)
ON CONFLICT (name) DO NOTHING;

-- Auto-register custom tools as MCP tools
INSERT INTO mcp_tools (name, description, input_schema, source_type, source_id)
SELECT ct.name, ct.description, ct.input_schema, 'custom_tool', ct.id
FROM custom_tools ct
WHERE ct.name IN ('calculate_ltv', 'revenue_summary', 'deal_win_rate')
ON CONFLICT DO NOTHING;

-- Seed built-in MCP tools (from MCP server)
INSERT INTO mcp_tools (name, description, input_schema, source_type, server_name) VALUES
    ('query_resource', 'Query a data resource using SQL or natural language',
     '{"type": "object", "properties": {"resource_uri": {"type": "string"}, "query": {"type": "string"}}, "required": ["resource_uri", "query"]}'::jsonb,
     'mcp_server', 'adf-mcp-server'),
    ('write_resource', 'Write data to a resource',
     '{"type": "object", "properties": {"resource_uri": {"type": "string"}, "payload": {"type": "object"}}, "required": ["resource_uri", "payload"]}'::jsonb,
     'mcp_server', 'adf-mcp-server'),
    ('mcp_tool_call', 'Call a tool on any running Docker MCP server',
     '{"type": "object", "properties": {"server": {"type": "string"}, "tool": {"type": "string"}, "arguments": {"type": "object"}}, "required": ["server", "tool", "arguments"]}'::jsonb,
     'mcp_server', 'adf-mcp-server'),
    ('create_connector', 'Create a new data connector',
     '{"type": "object", "properties": {"name": {"type": "string"}, "connector_type": {"type": "string"}, "config": {"type": "object"}}, "required": ["name", "connector_type", "config"]}'::jsonb,
     'mcp_server', 'adf-mcp-server'),
    ('create_tool', 'Create a new custom tool',
     '{"type": "object", "properties": {"name": {"type": "string"}, "description": {"type": "string"}, "code": {"type": "string"}, "input_schema": {"type": "object"}}, "required": ["name", "code"]}'::jsonb,
     'mcp_server', 'adf-mcp-server')
ON CONFLICT DO NOTHING;

-- =============================================================================
-- Dummy B2B Schema (for demo/testing)
-- =============================================================================

CREATE TABLE IF NOT EXISTS b2b_companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    industry TEXT,
    website TEXT,
    employee_count INT,
    annual_revenue NUMERIC(15,2),
    country TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS b2b_contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES b2b_companies(id) ON DELETE CASCADE,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    title TEXT,
    phone TEXT,
    is_primary BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS b2b_deals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES b2b_companies(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES b2b_contacts(id),
    deal_name TEXT NOT NULL,
    stage TEXT NOT NULL DEFAULT 'prospecting',
    amount NUMERIC(15,2),
    currency TEXT DEFAULT 'USD',
    probability INT DEFAULT 10,
    expected_close_date DATE,
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS b2b_invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id UUID REFERENCES b2b_deals(id) ON DELETE CASCADE,
    company_id UUID REFERENCES b2b_companies(id) ON DELETE CASCADE,
    invoice_number TEXT UNIQUE NOT NULL,
    amount NUMERIC(15,2) NOT NULL,
    currency TEXT DEFAULT 'USD',
    status TEXT NOT NULL DEFAULT 'pending',
    issued_date DATE NOT NULL DEFAULT CURRENT_DATE,
    due_date DATE,
    paid_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS b2b_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    sku TEXT UNIQUE NOT NULL,
    category TEXT,
    unit_price NUMERIC(12,2) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS b2b_order_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID REFERENCES b2b_invoices(id) ON DELETE CASCADE,
    product_id UUID REFERENCES b2b_products(id),
    quantity INT NOT NULL DEFAULT 1,
    unit_price NUMERIC(12,2) NOT NULL,
    discount_pct NUMERIC(5,2) DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seed B2B demo data
INSERT INTO b2b_companies (name, industry, website, employee_count, annual_revenue, country) VALUES
    ('Acme Corp', 'Manufacturing', 'https://acme.example.com', 500, 25000000.00, 'US'),
    ('Globex Industries', 'Technology', 'https://globex.example.com', 250, 15000000.00, 'US'),
    ('Initech Solutions', 'Consulting', 'https://initech.example.com', 120, 8000000.00, 'UK'),
    ('Hooli Inc', 'Technology', 'https://hooli.example.com', 1200, 95000000.00, 'US'),
    ('Pied Piper', 'Technology', 'https://piedpiper.example.com', 45, 3000000.00, 'US'),
    ('Stark Industries', 'Defense', 'https://stark.example.com', 8000, 500000000.00, 'US'),
    ('Wayne Enterprises', 'Conglomerate', 'https://wayne.example.com', 5000, 300000000.00, 'US'),
    ('Umbrella Corp', 'Pharmaceuticals', 'https://umbrella.example.com', 3000, 120000000.00, 'JP'),
    ('Cyberdyne Systems', 'AI/Robotics', 'https://cyberdyne.example.com', 600, 45000000.00, 'US'),
    ('Soylent Corp', 'Food & Beverage', 'https://soylent.example.com', 200, 12000000.00, 'US')
ON CONFLICT (name) DO NOTHING;

INSERT INTO b2b_contacts (company_id, first_name, last_name, email, title, phone, is_primary)
SELECT c.id, v.first_name, v.last_name, v.email, v.title, v.phone, v.is_primary
FROM (VALUES
    ('Acme Corp', 'John', 'Smith', 'john@acme.example.com', 'CTO', '+1-555-0101', true),
    ('Acme Corp', 'Jane', 'Doe', 'jane@acme.example.com', 'VP Engineering', '+1-555-0102', false),
    ('Globex Industries', 'Bob', 'Wilson', 'bob@globex.example.com', 'CEO', '+1-555-0201', true),
    ('Initech Solutions', 'Alice', 'Brown', 'alice@initech.example.com', 'Head of IT', '+44-555-0301', true),
    ('Hooli Inc', 'Gavin', 'Belson', 'gavin@hooli.example.com', 'CEO', '+1-555-0401', true),
    ('Pied Piper', 'Richard', 'Hendricks', 'richard@piedpiper.example.com', 'CEO', '+1-555-0501', true),
    ('Stark Industries', 'Pepper', 'Potts', 'pepper@stark.example.com', 'CEO', '+1-555-0601', true),
    ('Wayne Enterprises', 'Lucius', 'Fox', 'lucius@wayne.example.com', 'CTO', '+1-555-0701', true),
    ('Umbrella Corp', 'Albert', 'Wesker', 'albert@umbrella.example.com', 'Director', '+81-555-0801', true),
    ('Cyberdyne Systems', 'Miles', 'Dyson', 'miles@cyberdyne.example.com', 'Chief Scientist', '+1-555-0901', true)
) AS v(company_name, first_name, last_name, email, title, phone, is_primary)
JOIN b2b_companies c ON c.name = v.company_name
ON CONFLICT (email) DO NOTHING;

INSERT INTO b2b_products (name, sku, category, unit_price, description) VALUES
    ('Enterprise Platform License', 'ENT-PLAT-001', 'Software', 50000.00, 'Annual enterprise platform license'),
    ('Data Integration Module', 'DATA-INT-001', 'Software', 15000.00, 'Data integration and ETL module'),
    ('API Gateway', 'API-GW-001', 'Software', 25000.00, 'API gateway with rate limiting'),
    ('Support Premium', 'SUP-PREM-001', 'Services', 10000.00, '24/7 premium support package'),
    ('Consulting Hours (10h)', 'CON-10H-001', 'Services', 5000.00, '10 hours of expert consulting'),
    ('Training Package', 'TRN-PKG-001', 'Services', 3000.00, 'Team training and onboarding')
ON CONFLICT (sku) DO NOTHING;

INSERT INTO b2b_deals (company_id, deal_name, stage, amount, currency, probability, expected_close_date)
SELECT c.id, v.deal_name, v.stage, v.amount, 'USD', v.probability, v.close_date::date
FROM (VALUES
    ('Acme Corp', 'Acme Enterprise Rollout', 'closed_won', 120000.00, 95, '2026-01-15'),
    ('Globex Industries', 'Globex Data Platform', 'negotiation', 85000.00, 70, '2026-04-30'),
    ('Initech Solutions', 'Initech Integration Project', 'proposal', 45000.00, 40, '2026-05-15'),
    ('Hooli Inc', 'Hooli Cloud Migration', 'closed_won', 350000.00, 100, '2025-12-01'),
    ('Pied Piper', 'Pied Piper Starter Package', 'closed_won', 25000.00, 100, '2026-02-10'),
    ('Stark Industries', 'Stark Full Platform Deal', 'negotiation', 500000.00, 60, '2026-06-30'),
    ('Wayne Enterprises', 'Wayne Analytics Suite', 'prospecting', 200000.00, 20, '2026-09-01'),
    ('Umbrella Corp', 'Umbrella Research Platform', 'proposal', 150000.00, 45, '2026-07-15'),
    ('Cyberdyne Systems', 'Cyberdyne AI Integration', 'closed_lost', 95000.00, 0, '2026-03-01'),
    ('Soylent Corp', 'Soylent Data Pipeline', 'qualification', 60000.00, 30, '2026-08-01')
) AS v(company_name, deal_name, stage, amount, probability, close_date)
JOIN b2b_companies c ON c.name = v.company_name
ON CONFLICT DO NOTHING;

INSERT INTO b2b_invoices (deal_id, company_id, invoice_number, amount, status, issued_date, due_date)
SELECT d.id, d.company_id, v.invoice_number, v.amount, v.status, v.issued_date::date, v.due_date::date
FROM (VALUES
    ('Acme Enterprise Rollout', 'INV-2026-001', 60000.00, 'paid', '2026-01-20', '2026-02-20'),
    ('Acme Enterprise Rollout', 'INV-2026-002', 60000.00, 'paid', '2026-02-20', '2026-03-20'),
    ('Hooli Cloud Migration', 'INV-2025-010', 175000.00, 'paid', '2025-12-15', '2026-01-15'),
    ('Hooli Cloud Migration', 'INV-2026-003', 175000.00, 'pending', '2026-03-15', '2026-04-15'),
    ('Pied Piper Starter Package', 'INV-2026-004', 25000.00, 'paid', '2026-02-15', '2026-03-15'),
    ('Globex Data Platform', 'INV-2026-005', 42500.00, 'pending', '2026-03-01', '2026-04-01')
) AS v(deal_name, invoice_number, amount, status, issued_date, due_date)
JOIN b2b_deals d ON d.deal_name = v.deal_name
ON CONFLICT (invoice_number) DO NOTHING;

-- =============================================================================
-- Seed Default Connectors
-- =============================================================================

INSERT INTO connectors (name, connector_type, description, config, sync_mode, is_active, owner_id)
SELECT 'Local Filesystem', 'filesystem',
    'Local filesystem connector for reading files and directories',
    '{"base_path": "data/sample-files"}'::jsonb,
    'live', true, u.id
FROM users u WHERE u.email = 'admin@adf.local'
ON CONFLICT (name) DO NOTHING;

INSERT INTO connectors (name, connector_type, description, config, sync_mode, is_active, owner_id)
SELECT 'Azure Blob Storage', 'azure_blob',
    'Azure Blob Storage — update credentials in Settings (account_name, account_key, container_name)',
    '{"container_name": "", "storage_account_name": ""}'::jsonb,
    'live', false, u.id
FROM users u WHERE u.email = 'admin@adf.local'
ON CONFLICT (name) DO NOTHING;

INSERT INTO connectors (name, connector_type, description, config, sync_mode, is_active, owner_id)
SELECT 'B2B Demo Database', 'postgres',
    'Demo B2B database with companies, contacts, deals, invoices, and products',
    '{"host": "localhost", "port": 5436, "database": "agent_data_fabric", "schema": "public", "user": "adf_user", "password": "adf_secret_password_change_me"}'::jsonb,
    'live', true, u.id
FROM users u WHERE u.email = 'admin@adf.local'
ON CONFLICT (name) DO NOTHING;

INSERT INTO mcp_resources (uri, name, description, resource_type, source_type, mime_type) VALUES
    ('connector://filesystem/Local Filesystem', 'Local Filesystem', 'Local filesystem connector', 'data_resource', 'connector', 'application/json'),
    ('connector://azure_blob/Azure Blob Storage', 'Azure Blob Storage', 'Azure Blob Storage connector', 'data_resource', 'connector', 'application/json'),
    ('connector://postgres/B2B Demo Database', 'B2B Demo Database', 'Demo B2B database', 'data_resource', 'connector', 'application/json')
ON CONFLICT DO NOTHING;
