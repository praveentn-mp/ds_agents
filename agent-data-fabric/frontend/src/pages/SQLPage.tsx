import React, { useEffect, useState, useCallback } from 'react';
import { sqlApi, connectorApi } from '../api/client';
import type { Connector, SQLResult } from '../types';
import { Play, Clock, Loader2, Table, ChevronRight, ChevronDown, Database, Columns, Sparkles, Layers } from 'lucide-react';

interface TableInfo {
  schema: string;
  name: string;
  columns: { name: string; type: string; nullable: boolean; default: string | null }[];
}

interface VectorTableInfo {
  name: string;
  columns: { name: string; type: string }[];
  row_count: number;
}

interface SchemaData {
  tables: TableInfo[];
}

const SAMPLE_QUERIES: Record<string, { label: string; query: string }[]> = {
  b2b_companies: [
    { label: 'Top companies by revenue', query: 'SELECT name, industry, annual_revenue, employee_count, country\nFROM b2b_companies\nORDER BY annual_revenue DESC\nLIMIT 10' },
    { label: 'Companies by industry', query: 'SELECT industry, COUNT(*) as company_count, SUM(annual_revenue) as total_revenue\nFROM b2b_companies\nGROUP BY industry\nORDER BY total_revenue DESC' },
    { label: 'Companies by headcount', query: 'SELECT name, employee_count, annual_revenue,\n  ROUND(annual_revenue / NULLIF(employee_count,0), 2) as revenue_per_employee\nFROM b2b_companies\nORDER BY employee_count DESC' },
  ],
  b2b_deals: [
    { label: 'Deals by stage', query: 'SELECT stage, COUNT(*) as deal_count, SUM(amount) as total_amount,\n  ROUND(AVG(probability)) as avg_probability\nFROM b2b_deals\nGROUP BY stage\nORDER BY total_amount DESC' },
    { label: 'Won deals with company', query: 'SELECT d.deal_name, c.name as company, d.amount, d.expected_close_date\nFROM b2b_deals d\nJOIN b2b_companies c ON c.id = d.company_id\nWHERE d.stage = \'closed_won\'\nORDER BY d.amount DESC' },
    { label: 'Pipeline value by company', query: 'SELECT c.name, COUNT(d.id) as deals, SUM(d.amount) as pipeline_value\nFROM b2b_deals d\nJOIN b2b_companies c ON c.id = d.company_id\nWHERE d.stage NOT IN (\'closed_won\', \'closed_lost\')\nGROUP BY c.name\nORDER BY pipeline_value DESC' },
  ],
  b2b_invoices: [
    { label: 'Invoices by status', query: 'SELECT status, COUNT(*) as invoice_count, SUM(amount) as total_amount\nFROM b2b_invoices\nGROUP BY status\nORDER BY total_amount DESC' },
    { label: 'Pending invoices', query: 'SELECT i.invoice_number, c.name as company, i.amount, i.issued_date, i.due_date\nFROM b2b_invoices i\nJOIN b2b_companies c ON c.id = i.company_id\nWHERE i.status = \'pending\'\nORDER BY i.due_date' },
    { label: 'Revenue collected', query: 'SELECT c.name as company, SUM(i.amount) as total_paid\nFROM b2b_invoices i\nJOIN b2b_companies c ON c.id = i.company_id\nWHERE i.status = \'paid\'\nGROUP BY c.name\nORDER BY total_paid DESC' },
  ],
  b2b_contacts: [
    { label: 'All contacts with company', query: 'SELECT ct.first_name, ct.last_name, ct.title, ct.email, c.name as company\nFROM b2b_contacts ct\nJOIN b2b_companies c ON c.id = ct.company_id\nORDER BY c.name' },
    { label: 'Primary contacts', query: 'SELECT ct.first_name || \' \' || ct.last_name as name, ct.title, ct.email, c.name as company\nFROM b2b_contacts ct\nJOIN b2b_companies c ON c.id = ct.company_id\nWHERE ct.is_primary = true' },
  ],
  b2b_products: [
    { label: 'All products', query: 'SELECT name, sku, category, unit_price, description\nFROM b2b_products\nORDER BY unit_price DESC' },
    { label: 'Products by category', query: 'SELECT category, COUNT(*) as product_count, AVG(unit_price) as avg_price\nFROM b2b_products\nGROUP BY category' },
  ],
  b2b_order_items: [
    { label: 'Order items with details', query: 'SELECT p.name as product, oi.quantity, oi.unit_price,\n  ROUND(oi.quantity * oi.unit_price * (1 - oi.discount_pct/100), 2) as line_total\nFROM b2b_order_items oi\nJOIN b2b_products p ON p.id = oi.product_id\nORDER BY line_total DESC' },
  ],
};

const VECTOR_SAMPLE_QUERIES: Record<string, { label: string; query: string }[]> = {
  vec_table_index: [
    { label: 'All indexed tables', query: 'SELECT table_name, description, metadata, created_at\nFROM vec_table_index\nORDER BY created_at DESC' },
    { label: 'Table count by connector', query: 'SELECT connector_id, COUNT(*) as table_count\nFROM vec_table_index\nGROUP BY connector_id' },
  ],
  vec_column_index: [
    { label: 'All indexed columns', query: 'SELECT table_name, column_name, description, data_type\nFROM vec_column_index\nORDER BY table_name, column_name' },
    { label: 'Columns per table', query: 'SELECT table_name, COUNT(*) as column_count\nFROM vec_column_index\nGROUP BY table_name\nORDER BY column_count DESC' },
    { label: 'Indexable data types', query: 'SELECT data_type, COUNT(*) as col_count\nFROM vec_column_index\nGROUP BY data_type\nORDER BY col_count DESC' },
  ],
  vec_value_index: [
    { label: 'All indexed values', query: 'SELECT table_name, column_name, value_text\nFROM vec_value_index\nORDER BY table_name, column_name\nLIMIT 50' },
    { label: 'Values per column', query: 'SELECT table_name, column_name, COUNT(*) as value_count\nFROM vec_value_index\nGROUP BY table_name, column_name\nORDER BY value_count DESC' },
    { label: 'Search for a value', query: 'SELECT table_name, column_name, value_text\nFROM vec_value_index\nWHERE value_text ILIKE \'%search_term%\'\nLIMIT 20' },
  ],
  vec_chunk_index: [
    { label: 'All document chunks', query: 'SELECT source_file, chunk_index, LEFT(chunk_text, 100) as preview\nFROM vec_chunk_index\nORDER BY source_file, chunk_index\nLIMIT 50' },
    { label: 'Chunks per source file', query: 'SELECT source_file, COUNT(*) as chunk_count\nFROM vec_chunk_index\nGROUP BY source_file\nORDER BY chunk_count DESC' },
  ],
};

export default function SQLPage() {
  const [query, setQuery] = useState('SELECT name, industry, annual_revenue\nFROM b2b_companies\nORDER BY annual_revenue DESC\nLIMIT 10');
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [selectedConnector, setSelectedConnector] = useState('');
  const [result, setResult] = useState<SQLResult | null>(null);
  const [executing, setExecuting] = useState(false);
  const [error, setError] = useState('');

  // Schema browser state
  const [schema, setSchema] = useState<SchemaData | null>(null);
  const [loadingSchema, setLoadingSchema] = useState(false);
  const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set());

  // Vector schema state
  const [vectorTables, setVectorTables] = useState<VectorTableInfo[]>([]);
  const [expandedVectorTables, setExpandedVectorTables] = useState<Set<string>>(new Set());

  useEffect(() => {
    connectorApi.list().then((res) => {
      const pgConnectors = res.data.filter((c: Connector) => c.connector_type === 'postgres');
      setConnectors(pgConnectors);
      if (pgConnectors.length > 0) setSelectedConnector(pgConnectors[0].id);
    });
  }, []);

  // Load schema when connector changes
  useEffect(() => {
    if (!selectedConnector) return;
    setLoadingSchema(true);
    setSchema(null);
    sqlApi.schema(selectedConnector)
      .then((res) => setSchema(res.data))
      .catch(() => setSchema(null))
      .finally(() => setLoadingSchema(false));
  }, [selectedConnector]);

  // Load vector schema once
  useEffect(() => {
    sqlApi.vectorSchema()
      .then((res) => setVectorTables(res.data.tables || []))
      .catch(() => setVectorTables([]));
  }, []);

  const handleExecute = useCallback(async () => {
    if (!selectedConnector || !query.trim()) return;
    setExecuting(true);
    setError('');
    setResult(null);
    try {
      const res = await sqlApi.execute({ query, connector_id: selectedConnector });
      setResult(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Query execution failed');
    }
    setExecuting(false);
  }, [selectedConnector, query]);

  const toggleTable = (tableName: string) => {
    setExpandedTables((prev) => {
      const next = new Set(prev);
      if (next.has(tableName)) next.delete(tableName);
      else next.add(tableName);
      return next;
    });
  };

  const selectTable = (tableName: string) => {
    setQuery(`SELECT *\nFROM ${tableName}\nLIMIT 20`);
  };

  const applySampleQuery = (sql: string) => {
    setQuery(sql);
  };

  // Filter to only b2b_ tables for the sample queries section
  const b2bTables = schema?.tables.filter((t) => t.name.startsWith('b2b_')) || [];

  return (
    <div className="flex h-[calc(100vh-64px)]">
      {/* ── Left sidebar: Schema Browser ── */}
      <div className="w-72 border-r border-gray-200 bg-gray-50 flex flex-col overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200 bg-white">
          <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
            <Database className="w-4 h-4" />
            Schema Browser
          </div>
          <select
            value={selectedConnector}
            onChange={(e) => setSelectedConnector(e.target.value)}
            className="mt-2 w-full px-2 py-1.5 text-xs border border-gray-200 rounded-lg bg-white"
          >
            <option value="">Select connector...</option>
            {connectors.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>

        {/* Single scrollable area for all table groups and sample queries */}
        <div className="flex-1 overflow-y-auto">
          {loadingSchema && (
            <div className="flex items-center gap-2 px-4 py-6 text-xs text-gray-400">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />Loading schema...
            </div>
          )}

          {/* ── Data Tables ── */}
          {schema && schema.tables.length > 0 && (
            <div>
              <div className="px-4 py-2 bg-white border-b border-gray-100 sticky top-0 z-10">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-gray-600">
                  <Table className="w-3.5 h-3.5 text-brand-500" />
                  Data Tables
                  <span className="ml-auto text-[10px] font-normal text-gray-400">{schema.tables.length}</span>
                </div>
              </div>
              <div className="py-1">
                {schema.tables.map((table) => {
                  const fullName = table.schema === 'public' ? table.name : `${table.schema}.${table.name}`;
                  const isExpanded = expandedTables.has(fullName);
                  return (
                    <div key={fullName}>
                      <button
                        className="w-full flex items-center gap-1 px-3 py-1.5 text-xs hover:bg-gray-100 transition group"
                        onClick={() => toggleTable(fullName)}
                      >
                        {isExpanded ? <ChevronDown className="w-3 h-3 text-gray-400" /> : <ChevronRight className="w-3 h-3 text-gray-400" />}
                        <Table className="w-3 h-3 text-brand-500" />
                        <span className="font-medium text-gray-700 truncate">{table.name}</span>
                        <span className="ml-auto text-[10px] text-gray-400 opacity-0 group-hover:opacity-100 transition cursor-pointer"
                              onClick={(e) => { e.stopPropagation(); selectTable(fullName === table.name ? table.name : fullName); }}
                        >SELECT</span>
                      </button>
                      {isExpanded && (
                        <div className="ml-7 border-l border-gray-200">
                          {table.columns.map((col) => (
                            <div key={col.name} className="flex items-center gap-1.5 px-2 py-0.5 text-[11px] text-gray-500">
                              <Columns className="w-2.5 h-2.5 text-gray-300" />
                              <span className="text-gray-600">{col.name}</span>
                              <span className="text-gray-400 ml-auto">{col.type}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          {schema && schema.tables.length === 0 && (
            <p className="px-4 py-6 text-xs text-gray-400">No tables found</p>
          )}

          {/* ── Vector Index Tables ── */}
          {vectorTables.length > 0 && (
            <div className="border-t border-gray-200">
              <div className="px-4 py-2 bg-white border-b border-gray-100 sticky top-0 z-10">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-gray-600">
                  <Layers className="w-3.5 h-3.5 text-purple-500" />
                  Vector Index Tables
                  <span className="ml-auto text-[10px] font-normal text-gray-400">{vectorTables.length}</span>
                </div>
              </div>
              <div className="py-1">
                {vectorTables.map((vt) => {
                  const isExpanded = expandedVectorTables.has(vt.name);
                  return (
                    <div key={vt.name}>
                      <button
                        className="w-full flex items-center gap-1 px-3 py-1.5 text-xs hover:bg-gray-100 transition group"
                        onClick={() => {
                          setExpandedVectorTables((prev) => {
                            const next = new Set(prev);
                            if (next.has(vt.name)) next.delete(vt.name);
                            else next.add(vt.name);
                            return next;
                          });
                        }}
                      >
                        {isExpanded ? <ChevronDown className="w-3 h-3 text-gray-400" /> : <ChevronRight className="w-3 h-3 text-gray-400" />}
                        <Table className="w-3 h-3 text-purple-500" />
                        <span className="font-medium text-gray-700 truncate">{vt.name}</span>
                        <span className="ml-auto flex items-center gap-1">
                          <span className="text-[10px] text-gray-400">{vt.row_count.toLocaleString()}</span>
                          <span className="text-[10px] text-gray-400 opacity-0 group-hover:opacity-100 transition cursor-pointer"
                                onClick={(e) => { e.stopPropagation(); setQuery(`SELECT *\nFROM ${vt.name}\nLIMIT 20`); }}
                          >SELECT</span>
                        </span>
                      </button>
                      {isExpanded && (
                        <div className="ml-7 border-l border-gray-200">
                          {vt.columns.map((col) => (
                            <div key={col.name} className="flex items-center gap-1.5 px-2 py-0.5 text-[11px] text-gray-500">
                              <Columns className="w-2.5 h-2.5 text-gray-300" />
                              <span className="text-gray-600">{col.name}</span>
                              <span className="text-gray-400 ml-auto">{col.type}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ── Sample Queries ── */}
          {b2bTables.length > 0 && (
            <div className="border-t border-gray-200">
              <div className="px-4 py-2 bg-white border-b border-gray-100 sticky top-0 z-10">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-gray-600">
                  <Sparkles className="w-3.5 h-3.5 text-amber-500" />
                  Sample Queries
                </div>
              </div>
              <div className="py-1">
                {b2bTables.map((table) => {
                  const samples = SAMPLE_QUERIES[table.name];
                  if (!samples) return null;
                  return (
                    <div key={table.name}>
                      <div className="px-3 py-1 text-[10px] font-semibold text-gray-400 uppercase tracking-wide">{table.name}</div>
                      {samples.map((s, i) => (
                        <button
                          key={i}
                          className="w-full text-left px-4 py-1 text-xs text-brand-600 hover:bg-brand-50 hover:text-brand-700 transition truncate"
                          onClick={() => applySampleQuery(s.query)}
                          title={s.query}
                        >
                          {s.label}
                        </button>
                      ))}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ── Vector Index Queries ── */}
          {vectorTables.length > 0 && (
            <div className="border-t border-gray-200">
              <div className="px-4 py-2 bg-white border-b border-gray-100 sticky top-0 z-10">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-gray-600">
                  <Sparkles className="w-3.5 h-3.5 text-purple-500" />
                  Vector Index Queries
                </div>
              </div>
              <div className="py-1">
                {vectorTables.map((vt) => {
                  const samples = VECTOR_SAMPLE_QUERIES[vt.name];
                  if (!samples) return null;
                  return (
                    <div key={vt.name}>
                      <div className="px-3 py-1 text-[10px] font-semibold text-gray-400 uppercase tracking-wide">{vt.name}</div>
                      {samples.map((s, i) => (
                        <button
                          key={i}
                          className="w-full text-left px-4 py-1 text-xs text-purple-600 hover:bg-purple-50 hover:text-purple-700 transition truncate"
                          onClick={() => applySampleQuery(s.query)}
                          title={s.query}
                        >
                          {s.label}
                        </button>
                      ))}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Main area: Query editor + results ── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="p-4 pb-0">
          <h2 className="text-xl font-bold text-gray-900">SQL Explorer</h2>
          <p className="text-sm text-gray-500 mb-4">Execute queries against your connected databases</p>
        </div>

        <div className="px-4 pb-2">
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="flex items-center gap-3 px-4 py-2 border-b border-gray-100 bg-gray-50">
              <span className="text-xs text-gray-400 font-mono">SQL</span>
              <div className="ml-auto flex items-center gap-2">
                <span className="text-[10px] text-gray-400">⌘+Enter</span>
                <button
                  onClick={handleExecute}
                  disabled={executing || !selectedConnector}
                  className="flex items-center gap-1.5 px-3 py-1 bg-brand-600 text-white text-xs rounded-lg hover:bg-brand-700 disabled:opacity-40 transition"
                >
                  {executing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                  Execute
                </button>
              </div>
            </div>
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full px-4 py-3 font-mono text-sm border-none outline-none resize-none bg-white"
              rows={6}
              placeholder="SELECT * FROM ..."
              onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') handleExecute(); }}
            />
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="mx-4 mb-2 px-4 py-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg">
            {error}
          </div>
        )}

        {/* Results */}
        <div className="flex-1 overflow-auto px-4 pb-4">
          {result && (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-b">
                <div className="flex items-center gap-4 text-xs text-gray-500">
                  <span className="flex items-center gap-1"><Table className="w-3.5 h-3.5" /> {result.total} rows</span>
                  <span className="flex items-center gap-1"><Clock className="w-3.5 h-3.5" /> {result.latency_ms}ms</span>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      {result.columns.map((col) => (
                        <th key={col} className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase border-b whitespace-nowrap">{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {result.rows.map((row, i) => (
                      <tr key={i} className="hover:bg-gray-50">
                        {row.map((cell, j) => (
                          <td key={j} className="px-4 py-2 text-xs text-gray-700 font-mono whitespace-nowrap">{String(cell ?? 'NULL')}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
