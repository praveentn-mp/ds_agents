-- =============================================================================
-- Vector Index Schema for Agentic Data Fabric
-- Supports: table metadata, column metadata, value embeddings, unstructured chunks
-- =============================================================================

-- Master ingestion metadata — one row per ingested source
CREATE TABLE IF NOT EXISTS ingestion_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_id UUID NOT NULL REFERENCES connectors(id) ON DELETE CASCADE,
    source_file TEXT,                     -- filename or table origin
    table_name TEXT NOT NULL,             -- target postgres table
    table_description TEXT,               -- LLM-generated description
    row_count INT DEFAULT 0,
    column_count INT DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Column-level metadata — one row per column per ingested table
CREATE TABLE IF NOT EXISTS column_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ingestion_id UUID NOT NULL REFERENCES ingestion_metadata(id) ON DELETE CASCADE,
    table_name TEXT NOT NULL,
    column_name TEXT NOT NULL,
    data_type TEXT,                       -- inferred type: text, numeric, date, id, categorical, unstructured
    description TEXT,                     -- LLM-generated description
    sample_values TEXT,                   -- comma-sep sample values
    categories TEXT,                      -- for categorical columns, all unique values
    value_range TEXT,                     -- for numeric columns, min-max
    is_indexable BOOLEAN DEFAULT true,    -- false for id, uuid, numeric-only, date-only
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Vector indices (all use 384-dim for sentence-transformers/all-MiniLM-L6-v2) ──

-- Table-level index: one embedding per table
CREATE TABLE IF NOT EXISTS vec_table_index (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ingestion_id UUID NOT NULL REFERENCES ingestion_metadata(id) ON DELETE CASCADE,
    connector_id UUID NOT NULL REFERENCES connectors(id) ON DELETE CASCADE,
    table_name TEXT NOT NULL,
    description TEXT NOT NULL,
    embedding vector(384),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Column-level index: one embedding per column
CREATE TABLE IF NOT EXISTS vec_column_index (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ingestion_id UUID NOT NULL REFERENCES ingestion_metadata(id) ON DELETE CASCADE,
    connector_id UUID NOT NULL REFERENCES connectors(id) ON DELETE CASCADE,
    table_name TEXT NOT NULL,
    column_name TEXT NOT NULL,
    description TEXT NOT NULL,
    data_type TEXT,
    embedding vector(384),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Value-level index: embeddings for categorical/text values
CREATE TABLE IF NOT EXISTS vec_value_index (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ingestion_id UUID NOT NULL REFERENCES ingestion_metadata(id) ON DELETE CASCADE,
    connector_id UUID NOT NULL REFERENCES connectors(id) ON DELETE CASCADE,
    table_name TEXT NOT NULL,
    column_name TEXT NOT NULL,
    value_text TEXT NOT NULL,
    embedding vector(384),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Unstructured chunk index: embeddings for document chunks
CREATE TABLE IF NOT EXISTS vec_chunk_index (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_id UUID NOT NULL REFERENCES connectors(id) ON DELETE CASCADE,
    source_file TEXT NOT NULL,
    chunk_index INT NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding vector(384),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Indices for vector search ──
CREATE INDEX IF NOT EXISTS idx_vec_table_embedding ON vec_table_index USING ivfflat (embedding vector_cosine_ops) WITH (lists = 20);
CREATE INDEX IF NOT EXISTS idx_vec_column_embedding ON vec_column_index USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);
CREATE INDEX IF NOT EXISTS idx_vec_value_embedding ON vec_value_index USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_vec_chunk_embedding ON vec_chunk_index USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Lookup indices
CREATE INDEX IF NOT EXISTS idx_ingestion_connector ON ingestion_metadata(connector_id);
CREATE INDEX IF NOT EXISTS idx_column_meta_ingestion ON column_metadata(ingestion_id);
CREATE INDEX IF NOT EXISTS idx_vec_table_connector ON vec_table_index(connector_id);
CREATE INDEX IF NOT EXISTS idx_vec_column_connector ON vec_column_index(connector_id);
CREATE INDEX IF NOT EXISTS idx_vec_value_connector ON vec_value_index(connector_id);
CREATE INDEX IF NOT EXISTS idx_vec_chunk_connector ON vec_chunk_index(connector_id);
