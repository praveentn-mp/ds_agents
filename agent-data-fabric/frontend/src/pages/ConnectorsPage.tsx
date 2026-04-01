import React, { useEffect, useState } from 'react';
import { connectorApi } from '../api/client';
import type { Connector } from '../types';
import {
  Database, Plus, Trash2, RefreshCw, CheckCircle2, XCircle, Loader2,
  Settings, Save, X, Download, Table, FileText, ArrowRight, ChevronDown, ChevronRight,
  Check,
} from 'lucide-react';

interface KV { [key: string]: string }

interface IngestionProgress {
  step: string;
  progress: number;
  file?: string;
  row_count?: number;
  chunks?: number;
  error?: string;
  counts?: { tables?: number; columns?: number; values?: number; chunks?: number; rows?: number };
}

interface DataSummary {
  connector_id: string;
  ingestions: { id: string; source_file: string; table_name: string; table_description: string; row_count: number; column_count: number; created_at: string }[];
  vector_counts: { tables: number; columns: number; values: number; chunks: number };
  total_rows: number;
  // Legacy fields
  tables?: { name: string; row_count?: number; column_count?: number; source?: string }[];
  documents?: { id: string; source: string; title: string; chunks: number }[];
  last_synced_at?: string | null;
}

const CONNECTOR_FIELDS: Record<string, { label: string; key: string; placeholder: string; secret?: boolean }[]> = {
  postgres: [
    { label: 'Host', key: 'host', placeholder: 'localhost' },
    { label: 'Port', key: 'port', placeholder: '5432' },
    { label: 'Database', key: 'database', placeholder: 'mydb' },
    { label: 'User', key: 'user', placeholder: 'postgres' },
    { label: 'Password', key: 'password', placeholder: '••••••••', secret: true },
    { label: 'Schema', key: 'schema', placeholder: 'public' },
  ],
  azure_blob: [
    { label: 'Account Name', key: 'storage_account_name', placeholder: 'mystorageaccount' },
    { label: 'Account Key', key: 'account_key', placeholder: '••••••••', secret: true },
    { label: 'Container Name', key: 'container_name', placeholder: 'my-container' },
    { label: 'Connection String', key: 'connection_string', placeholder: 'DefaultEndpointsProtocol=https;...', secret: true },
  ],
  filesystem: [
    { label: 'Base Path', key: 'base_path', placeholder: '/path/to/files' },
  ],
};

const TYPE_DESC: Record<string, string> = {
  postgres: 'Structured data — tables are queried live via SQL. Use the Chat or SQL Explorer to analyze.',
  azure_blob: 'Files in cloud storage. Ingest to load structured data (CSV/JSON) as tables and index documents for RAG search.',
  filesystem: 'Local files. Ingest to load structured data (CSV/JSON) as tables and index documents for RAG search.',
};

function FieldForm({ fields, config, creds, onConfigChange, onCredsChange }: {
  fields: typeof CONNECTOR_FIELDS['postgres']; config: KV; creds: KV;
  onConfigChange: (c: KV) => void; onCredsChange: (c: KV) => void;
}) {
  return (
    <div className="space-y-3">
      {fields.map((f) => (
        <div key={f.key}>
          <label className="block text-sm font-medium text-gray-700 mb-1">{f.label}</label>
          <input
            type={f.secret ? 'password' : 'text'}
            placeholder={f.placeholder}
            value={f.secret ? (creds[f.key] ?? '') : (config[f.key] ?? '')}
            onChange={(e) =>
              f.secret
                ? onCredsChange({ ...creds, [f.key]: e.target.value })
                : onConfigChange({ ...config, [f.key]: e.target.value })
            }
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
      ))}
    </div>
  );
}

function ProgressBar({ progress }: { progress: number }) {
  return (
    <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
      <div
        className="bg-brand-500 h-2 rounded-full transition-all duration-500 ease-out"
        style={{ width: `${Math.min(progress, 100)}%` }}
      />
    </div>
  );
}

function DataSummaryPanel({ summary, onReindex, onDeleteData, isReindexing }: {
  summary: DataSummary | null; onReindex: () => void; onDeleteData: () => void; isReindexing?: boolean;
}) {
  if (!summary) return null;
  const hasIngestions = summary.ingestions && summary.ingestions.length > 0;
  const hasVectors = summary.vector_counts && (
    summary.vector_counts.tables > 0 || summary.vector_counts.columns > 0 ||
    summary.vector_counts.values > 0 || summary.vector_counts.chunks > 0
  );
  // Legacy support
  const hasTables = summary.tables && summary.tables.length > 0;
  const hasDocs = summary.documents && summary.documents.length > 0;

  if (!hasIngestions && !hasVectors && !hasTables && !hasDocs) return null;

  return (
    <div className="mt-3 pt-3 border-t border-gray-100 space-y-3">
      {/* Vector index counts */}
      {hasVectors && (
        <div>
          <div className="flex items-center gap-1.5 text-xs font-semibold text-gray-500 mb-2">
            <Database className="w-3 h-3" /> Vector Index
          </div>
          <div className="grid grid-cols-4 gap-2">
            {[
              { label: 'Tables', count: summary.vector_counts.tables, color: 'bg-blue-50 text-blue-700' },
              { label: 'Columns', count: summary.vector_counts.columns, color: 'bg-purple-50 text-purple-700' },
              { label: 'Values', count: summary.vector_counts.values, color: 'bg-amber-50 text-amber-700' },
              { label: 'Chunks', count: summary.vector_counts.chunks, color: 'bg-green-50 text-green-700' },
            ].map((item) => (
              <div key={item.label} className={`rounded-lg px-2.5 py-1.5 text-center ${item.color}`}>
                <div className="text-sm font-bold">{item.count.toLocaleString()}</div>
                <div className="text-[10px] opacity-75">{item.label}</div>
              </div>
            ))}
          </div>
          {summary.total_rows > 0 && (
            <p className="text-[10px] text-gray-400 mt-1">{summary.total_rows.toLocaleString()} total rows across all tables</p>
          )}
        </div>
      )}

      {/* Ingestion details */}
      {hasIngestions && (
        <div>
          <div className="flex items-center gap-1.5 text-xs font-semibold text-gray-500 mb-1">
            <Table className="w-3 h-3" /> Ingested Tables
          </div>
          {summary.ingestions.map((ing) => (
            <div key={ing.id} className="flex items-center justify-between text-xs text-gray-600 px-2 py-1">
              <div className="min-w-0">
                <span className="font-mono">{ing.table_name}</span>
                {ing.table_description && (
                  <span className="ml-1.5 text-gray-400">— {ing.table_description}</span>
                )}
              </div>
              <span className="text-gray-400 whitespace-nowrap ml-2">
                {ing.row_count?.toLocaleString()} rows · {ing.column_count} cols
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Legacy tables */}
      {hasTables && !hasIngestions && (
        <div>
          <div className="flex items-center gap-1.5 text-xs font-semibold text-gray-500 mb-1">
            <Table className="w-3 h-3" /> Tables
          </div>
          {summary.tables!.map((t) => (
            <div key={t.name} className="flex items-center justify-between text-xs text-gray-600 px-2 py-0.5">
              <span className="font-mono">{t.name}</span>
              <span className="text-gray-400">
                {t.row_count != null ? `${t.row_count.toLocaleString()} rows` : `${t.column_count} cols`}
                {t.source === 'live' && <span className="ml-1 text-green-500">● live</span>}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Legacy docs */}
      {hasDocs && (
        <div>
          <div className="flex items-center gap-1.5 text-xs font-semibold text-gray-500 mb-1">
            <FileText className="w-3 h-3" /> RAG Documents
          </div>
          {summary.documents!.map((d) => (
            <div key={d.id} className="flex items-center justify-between text-xs text-gray-600 px-2 py-0.5">
              <span className="truncate max-w-[160px]">{d.title}</span>
              <span className="text-gray-400">{d.chunks} chunks</span>
            </div>
          ))}
        </div>
      )}

      {/* Actions: reindex + delete */}
      {(hasIngestions || hasVectors) && (
        <div className="flex items-center gap-2 pt-2 border-t border-gray-100">
          <button
            onClick={onReindex}
            disabled={isReindexing}
            className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-blue-600 bg-blue-50 rounded-lg hover:bg-blue-100 disabled:opacity-50 transition"
          >
            {isReindexing ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
            Re-index
          </button>
          <button
            onClick={onDeleteData}
            className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-red-600 bg-red-50 rounded-lg hover:bg-red-100 transition"
          >
            <Trash2 className="w-3 h-3" /> Delete All Data
          </button>
        </div>
      )}

      {summary.last_synced_at && (
        <p className="text-[10px] text-gray-400">
          Last synced: {new Date(summary.last_synced_at).toLocaleString()}
        </p>
      )}
    </div>
  );
}

export default function ConnectorsPage() {
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [testResults, setTestResults] = useState<Record<string, { success: boolean; message: string }>>({});
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Add form
  const [addName, setAddName] = useState('');
  const [addType, setAddType] = useState('postgres');
  const [addDesc, setAddDesc] = useState('');
  const [addConfig, setAddConfig] = useState<KV>({});
  const [addCreds, setAddCreds] = useState<KV>({});

  // Edit form
  const [editConfig, setEditConfig] = useState<KV>({});
  const [editCreds, setEditCreds] = useState<KV>({});

  // Ingestion
  const [ingesting, setIngesting] = useState<Record<string, boolean>>({});
  const [ingestionProgress, setIngestionProgress] = useState<Record<string, IngestionProgress>>({});
  const [ingestionLogs, setIngestionLogs] = useState<Record<string, string[]>>({});

  // Data summary
  const [dataSummaries, setDataSummaries] = useState<Record<string, DataSummary>>({});

  // Table/file selection picker
  const [tablePickerConnector, setTablePickerConnector] = useState<Connector | null>(null);
  const [availableTables, setAvailableTables] = useState<{ schema: string; name: string }[]>([]);
  const [availableFiles, setAvailableFiles] = useState<{ name: string; size?: number; container?: string }[]>([]);
  const [selectedTables, setSelectedTables] = useState<string[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);
  const [loadingTables, setLoadingTables] = useState(false);

  const fetchConnectors = async () => {
    setLoading(true);
    try { setConnectors((await connectorApi.list()).data); } catch (err) { console.error(err); }
    setLoading(false);
  };

  useEffect(() => { fetchConnectors(); }, []);

  // Load data summary when a connector is expanded
  useEffect(() => {
    if (expandedId) {
      connectorApi.dataSummary(expandedId)
        .then((res) => setDataSummaries((p) => ({ ...p, [expandedId]: res.data })))
        .catch(() => {});
    }
  }, [expandedId]);

  const resetAddForm = () => { setAddName(''); setAddType('postgres'); setAddDesc(''); setAddConfig({}); setAddCreds({}); };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const config: Record<string, any> = { ...addConfig };
      if (config.port) config.port = parseInt(config.port, 10) || config.port;
      const creds = { ...addCreds };
      const hasC = Object.values(creds).some(v => v !== '');
      await connectorApi.create({ name: addName, connector_type: addType, description: addDesc, config, credentials: hasC ? creds : undefined });
      setShowAdd(false); resetAddForm(); fetchConnectors();
    } catch (err: any) { alert(err.response?.data?.detail || 'Failed to create connector'); }
  };

  const handleTest = async (id: string) => {
    setTestResults((p) => ({ ...p, [id]: { success: false, message: 'Testing...' } }));
    try {
      const res = await connectorApi.test(id);
      setTestResults((p) => ({ ...p, [id]: res.data }));
      if (res.data.success) fetchConnectors();
    }
    catch { setTestResults((p) => ({ ...p, [id]: { success: false, message: 'Test failed' } })); }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this connector?')) return;
    try { await connectorApi.delete(id); fetchConnectors(); } catch (err: any) { alert(err.response?.data?.detail || 'Failed'); }
  };

  const handleIngest = async (id: string, opts?: { tableNames?: string[]; fileNames?: string[] }) => {
    setIngesting((p) => ({ ...p, [id]: true }));
    setIngestionLogs((p) => ({ ...p, [id]: [] }));
    setIngestionProgress((p) => ({ ...p, [id]: { step: 'Starting...', progress: 0 } }));
    setExpandedId(id);

    const token = localStorage.getItem('adf_token');
    try {
      const payload: any = {};
      if (opts?.tableNames && opts.tableNames.length > 0) payload.table_names = opts.tableNames;
      if (opts?.fileNames && opts.fileNames.length > 0) payload.file_names = opts.fileNames;
      const body = Object.keys(payload).length > 0 ? JSON.stringify(payload) : undefined;
      const response = await fetch(`/api/connectors/${id}/ingest`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          ...(body ? { 'Content-Type': 'application/json' } : {}),
        },
        body,
      });
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) return;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const text = decoder.decode(value, { stream: true });
        for (const line of text.split('\n')) {
          if (line.startsWith('data: ')) {
            try {
              const evt = JSON.parse(line.slice(6));
              if (evt.event === 'ingestion_progress') {
                setIngestionProgress((p) => ({ ...p, [id]: evt.data }));
                setIngestionLogs((p) => ({
                  ...p,
                  [id]: [...(p[id] || []), evt.data.step],
                }));
              } else if (evt.event === 'ingestion_done') {
                setIngestionProgress((p) => ({ ...p, [id]: { step: 'Ingestion complete', progress: 100 } }));
              } else if (evt.event === 'error') {
                setIngestionProgress((p) => ({ ...p, [id]: { step: `Error: ${evt.data.message}`, progress: 0, error: evt.data.message } }));
              }
            } catch {}
          }
        }
      }
    } catch (e: any) {
      setIngestionProgress((p) => ({ ...p, [id]: { step: `Error: ${e.message}`, progress: 0, error: e.message } }));
    }

    setIngesting((p) => ({ ...p, [id]: false }));
    fetchConnectors();
    // Refresh data summary
    connectorApi.dataSummary(id)
      .then((res) => setDataSummaries((p) => ({ ...p, [id]: res.data })))
      .catch(() => {});
  };

  const openTablePicker = async (c: Connector) => {
    setTablePickerConnector(c);
    setLoadingTables(true);
    setSelectedTables([]);
    setSelectedFiles([]);
    setAvailableTables([]);
    setAvailableFiles([]);
    try {
      const res = await connectorApi.discoverSchema(c.id);
      if (c.connector_type === 'postgres') {
        const tables = (res.data.schema_json?.tables || []).map((t: any) => ({
          schema: t.schema,
          name: t.name,
        }));
        setAvailableTables(tables);
        setSelectedTables(tables.map((t: { schema: string; name: string }) => t.name));
      } else if (c.connector_type === 'azure_blob') {
        const files: { name: string; size?: number; container?: string }[] = [];
        for (const container of (res.data.schema_json?.containers || [])) {
          for (const blob of (container.blobs || [])) {
            files.push({ name: blob.name, size: blob.size, container: container.name });
          }
        }
        setAvailableFiles(files);
        setSelectedFiles(files.map((f) => f.name));
      } else if (c.connector_type === 'filesystem') {
        const files: { name: string; size?: number }[] = [];
        for (const dir of (res.data.schema_json?.directories || [])) {
          for (const f of (dir.files || [])) {
            files.push({ name: f.name, size: f.size });
          }
        }
        setAvailableFiles(files);
        setSelectedFiles(files.map((f) => f.name));
      }
    } catch (err) {
      console.error('Failed to discover schema', err);
    }
    setLoadingTables(false);
  };

  const handleStartIngestWithTables = () => {
    if (!tablePickerConnector) return;
    const id = tablePickerConnector.id;
    const type = tablePickerConnector.connector_type;
    setTablePickerConnector(null);
    if (type === 'postgres') {
      handleIngest(id, { tableNames: selectedTables.length > 0 ? selectedTables : undefined });
    } else {
      handleIngest(id, { fileNames: selectedFiles.length > 0 ? selectedFiles : undefined });
    }
  };

  const handleReindex = async (id: string) => {
    if (!confirm('Re-index this connector? This will re-generate all vector embeddings.')) return;
    setIngesting((p) => ({ ...p, [id]: true }));
    setIngestionLogs((p) => ({ ...p, [id]: ['Re-indexing...'] }));
    setIngestionProgress((p) => ({ ...p, [id]: { step: 'Re-indexing...', progress: 0 } }));
    setExpandedId(id);

    const token = localStorage.getItem('adf_token');
    try {
      const response = await fetch(`/api/connectors/${id}/reindex`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) return;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const text = decoder.decode(value, { stream: true });
        for (const line of text.split('\n')) {
          if (line.startsWith('data: ')) {
            try {
              const evt = JSON.parse(line.slice(6));
              if (evt.event === 'ingestion_progress' || evt.event === 'reindex_start') {
                const data = evt.data;
                setIngestionProgress((p) => ({ ...p, [id]: { step: data.step || data.message, progress: data.progress || 0, counts: data.counts } }));
                setIngestionLogs((p) => ({
                  ...p,
                  [id]: [...(p[id] || []), data.step || data.message],
                }));
              } else if (evt.event === 'ingestion_done') {
                setIngestionProgress((p) => ({ ...p, [id]: { step: 'Re-index complete', progress: 100 } }));
              }
            } catch {}
          }
        }
      }
    } catch (e: any) {
      setIngestionProgress((p) => ({ ...p, [id]: { step: `Error: ${e.message}`, progress: 0, error: e.message } }));
    }

    setIngesting((p) => ({ ...p, [id]: false }));
    fetchConnectors();
    connectorApi.dataSummary(id)
      .then((res) => setDataSummaries((p) => ({ ...p, [id]: res.data })))
      .catch(() => {});
  };

  const handleDeleteData = async (id: string) => {
    if (!confirm('Delete ALL ingested data and vector indices for this connector? This cannot be undone.')) return;
    try {
      await connectorApi.deleteData(id);
      setDataSummaries((p) => {
        const copy = { ...p };
        delete copy[id];
        return copy;
      });
      setIngestionProgress((p) => {
        const copy = { ...p };
        delete copy[id];
        return copy;
      });
      setIngestionLogs((p) => {
        const copy = { ...p };
        delete copy[id];
        return copy;
      });
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to delete data');
    }
  };

  const openSettings = (c: Connector) => {
    setEditingId(c.id);
    const cfg: KV = {};
    if (c.config) Object.entries(c.config).forEach(([k, v]) => { cfg[k] = String(v ?? ''); });
    setEditConfig(cfg); setEditCreds({});
  };

  const handleSaveSettings = async () => {
    if (!editingId) return;
    setSaving(true);
    try {
      const config: Record<string, any> = { ...editConfig };
      if (config.port) config.port = parseInt(config.port, 10) || config.port;
      const payload: any = { config };
      if (Object.values(editCreds).some(v => v !== '' && v !== undefined)) payload.credentials = editCreds;
      await connectorApi.update(editingId, payload);
      setEditingId(null); fetchConnectors();
    } catch (err: any) { alert(err.response?.data?.detail || 'Failed to save'); }
    setSaving(false);
  };

  const typeIcon: Record<string, string> = { postgres: '🐘', azure_blob: '☁️', filesystem: '📁' };
  const editingConnector = connectors.find((c) => c.id === editingId);

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Data Sources</h2>
          <p className="text-sm text-gray-500">Connect, ingest, and manage your data sources</p>
        </div>
        <div className="flex gap-2">
          <button onClick={fetchConnectors} className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 transition"><RefreshCw className="w-4 h-4" /></button>
          <button onClick={() => { resetAddForm(); setShowAdd(true); }} className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 transition"><Plus className="w-4 h-4" /> Add Data Source</button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 text-brand-500 animate-spin" /></div>
      ) : connectors.length === 0 ? (
        <div className="text-center py-20 bg-white rounded-xl border border-gray-200">
          <Database className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 mb-1">No data sources connected yet</p>
          <p className="text-xs text-gray-400 mb-4">Connect a database, cloud storage, or local files to get started</p>
          <button onClick={() => { resetAddForm(); setShowAdd(true); }} className="px-4 py-2 bg-brand-600 text-white text-sm rounded-lg hover:bg-brand-700 transition">Add Your First Data Source</button>
        </div>
      ) : (
        <div className="space-y-4">
          {connectors.map((c) => {
            const isExpanded = expandedId === c.id;
            const progress = ingestionProgress[c.id];
            const isIngesting = ingesting[c.id];
            const logs = ingestionLogs[c.id] || [];
            const summary = dataSummaries[c.id];

            return (
              <div key={c.id} className="bg-white rounded-xl border border-gray-200 overflow-hidden hover:shadow-sm transition">
                {/* Header row */}
                <div className="p-5">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      <span className="text-2xl">{typeIcon[c.connector_type] || '🔌'}</span>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <h3 className="font-semibold text-gray-900 truncate">{c.name}</h3>
                          <span className={`px-2 py-0.5 text-xs rounded-full whitespace-nowrap ${c.is_active ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                            {c.is_active ? 'Active' : 'Inactive'}
                          </span>
                        </div>
                        <p className="text-xs text-gray-400">{TYPE_DESC[c.connector_type] || c.connector_type}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5 ml-4">
                      <button onClick={() => handleTest(c.id)} className="px-3 py-1.5 text-xs font-medium text-brand-600 bg-brand-50 rounded-lg hover:bg-brand-100 transition">Test</button>
                      {c.is_active && (
                        <button
                          onClick={() => openTablePicker(c)}
                          disabled={isIngesting}
                          className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-amber-700 bg-amber-50 rounded-lg hover:bg-amber-100 disabled:opacity-50 transition"
                        >
                          {isIngesting ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />}
                          {c.connector_type === 'postgres' ? 'Index' : 'Ingest'}
                        </button>
                      )}
                      <button onClick={() => setExpandedId(isExpanded ? null : c.id)}
                        className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-50 rounded-lg transition" title="Details">
                        {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                      </button>
                      <button onClick={() => openSettings(c)} className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-50 rounded-lg transition" title="Settings"><Settings className="w-3.5 h-3.5" /></button>
                      <button onClick={() => handleDelete(c.id)} className="p-1.5 text-red-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition" title="Delete"><Trash2 className="w-3.5 h-3.5" /></button>
                    </div>
                  </div>

                  {/* Test result */}
                  {testResults[c.id] && (
                    <div className={`flex items-center gap-2 text-xs mt-3 ${testResults[c.id].success ? 'text-green-600' : 'text-red-600'}`}>
                      {testResults[c.id].success ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                      <span>{testResults[c.id].message}</span>
                      {testResults[c.id].success && !isIngesting && (
                        <button onClick={() => openTablePicker(c)} className="ml-2 flex items-center gap-1 text-amber-600 hover:text-amber-700 font-medium">
                          <ArrowRight className="w-3 h-3" /> {c.connector_type === 'postgres' ? 'Index data now' : 'Ingest data now'}
                        </button>
                      )}
                    </div>
                  )}

                  {/* Ingestion progress */}
                  {progress && (
                    <div className="mt-3 space-y-1.5">
                      <ProgressBar progress={progress.progress} />
                      <p className="text-xs text-gray-500">{progress.step}</p>
                      {progress.counts && (
                        <div className="flex gap-3 text-[10px] text-gray-400">
                          {progress.counts.tables != null && <span>Tables: {progress.counts.tables}</span>}
                          {progress.counts.columns != null && <span>Columns: {progress.counts.columns}</span>}
                          {progress.counts.values != null && <span>Values: {progress.counts.values}</span>}
                          {progress.counts.chunks != null && <span>Chunks: {progress.counts.chunks}</span>}
                          {progress.counts.rows != null && <span>Rows: {progress.counts.rows.toLocaleString()}</span>}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Expanded details */}
                {isExpanded && (
                  <div className="px-5 pb-5 border-t border-gray-100">
                    {/* Ingestion log */}
                    {logs.length > 0 && (
                      <div className="mt-3">
                        <p className="text-xs font-semibold text-gray-500 mb-1">Ingestion Log</p>
                        <div className="max-h-32 overflow-y-auto bg-gray-50 rounded-lg p-2 text-xs text-gray-600 space-y-0.5 font-mono">
                          {logs.map((log, i) => (
                            <div key={i} className="flex items-start gap-1.5">
                              <span className="text-gray-400 select-none">{String(i + 1).padStart(2, ' ')}.</span>
                              <span>{log}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Data summary */}
                    <DataSummaryPanel
                      summary={summary || null}
                      onReindex={() => handleReindex(c.id)}
                      onDeleteData={() => handleDeleteData(c.id)}
                      isReindexing={isIngesting}
                    />

                    {!summary && !logs.length && (
                      <p className="mt-3 text-xs text-gray-400 italic">
                        {c.connector_type === 'postgres'
                          ? 'Click "Index" to analyze schema and build vector search indices for intelligent querying.'
                          : 'Click "Ingest" to load data from this source into the platform.'}
                      </p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Add Connector Modal */}
      {showAdd && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setShowAdd(false)}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6 max-h-[85vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-lg font-semibold text-gray-900">Add Data Source</h3>
              <button onClick={() => setShowAdd(false)} className="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100"><X className="w-4 h-4" /></button>
            </div>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                <input value={addName} onChange={(e) => setAddName(e.target.value)} className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" required />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Type</label>
                <select value={addType} onChange={(e) => { setAddType(e.target.value); setAddConfig({}); setAddCreds({}); }} className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
                  <option value="postgres">PostgreSQL Database</option>
                  <option value="azure_blob">Azure Blob Storage</option>
                  <option value="filesystem">Local Filesystem</option>
                </select>
                <p className="text-xs text-gray-400 mt-1">{TYPE_DESC[addType]}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <input value={addDesc} onChange={(e) => setAddDesc(e.target.value)} className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </div>
              <div className="pt-2 border-t border-gray-100">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Connection Settings</p>
                <FieldForm fields={CONNECTOR_FIELDS[addType] || []} config={addConfig} creds={addCreds} onConfigChange={setAddConfig} onCredsChange={setAddCreds} />
              </div>
              <div className="flex gap-3 justify-end pt-4 border-t border-gray-100">
                <button type="button" onClick={() => setShowAdd(false)} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition">Cancel</button>
                <button type="submit" className="px-4 py-2 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700 transition">Create</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Settings Modal */}
      {editingId && editingConnector && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setEditingId(null)}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6 max-h-[85vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3">
                <span className="text-2xl">{typeIcon[editingConnector.connector_type] || '🔌'}</span>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">{editingConnector.name}</h3>
                  <p className="text-xs text-gray-400 capitalize">{editingConnector.connector_type.replace('_', ' ')} settings</p>
                </div>
              </div>
              <button onClick={() => setEditingId(null)} className="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100"><X className="w-4 h-4" /></button>
            </div>
            <FieldForm fields={CONNECTOR_FIELDS[editingConnector.connector_type] || []} config={editConfig} creds={editCreds} onConfigChange={setEditConfig} onCredsChange={setEditCreds} />
            <div className="flex gap-3 justify-end mt-6 pt-4 border-t border-gray-100">
              <button onClick={() => setEditingId(null)} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition">Cancel</button>
              <button onClick={handleSaveSettings} disabled={saving} className="flex items-center gap-2 px-4 py-2 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 transition">
                {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />} Save Settings
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Table/File Selection Modal */}
      {tablePickerConnector && (() => {
        const isPostgres = tablePickerConnector.connector_type === 'postgres';
        const items = isPostgres ? availableTables : availableFiles;
        const selected = isPostgres ? selectedTables : selectedFiles;
        const setSelected = isPostgres ? setSelectedTables : setSelectedFiles;
        const itemNames = isPostgres
          ? availableTables.map((t) => t.name)
          : availableFiles.map((f) => f.name);
        const label = isPostgres ? 'Tables' : 'Files';
        const actionLabel = isPostgres ? 'Index' : 'Ingest';

        return (
          <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setTablePickerConnector(null)}>
            <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6 max-h-[85vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">Select {label} to {actionLabel}</h3>
                  <p className="text-xs text-gray-400 mt-0.5">{tablePickerConnector.name} — choose which {label.toLowerCase()} to include</p>
                </div>
                <button onClick={() => setTablePickerConnector(null)} className="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100"><X className="w-4 h-4" /></button>
              </div>

              {loadingTables ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-6 h-6 text-brand-500 animate-spin" />
                  <span className="ml-2 text-sm text-gray-500">Discovering {label.toLowerCase()}...</span>
                </div>
              ) : items.length === 0 ? (
                <p className="text-sm text-gray-500 py-8 text-center">No {label.toLowerCase()} found. Make sure the connector is properly configured and tested.</p>
              ) : (
                <>
                  <div className="flex items-center justify-between mb-3 pb-2 border-b border-gray-100">
                    <span className="text-xs text-gray-500">{selected.length} of {items.length} {label.toLowerCase()} selected</span>
                    <div className="flex gap-2">
                      <button onClick={() => setSelected(itemNames)} className="text-xs text-brand-600 hover:text-brand-700 font-medium">Select All</button>
                      <button onClick={() => setSelected([])} className="text-xs text-gray-500 hover:text-gray-700 font-medium">Clear</button>
                    </div>
                  </div>
                  <div className="space-y-1 max-h-80 overflow-y-auto">
                    {isPostgres ? availableTables.map((t) => {
                      const isSelected = selectedTables.includes(t.name);
                      return (
                        <label key={`${t.schema}.${t.name}`} className={`flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer transition ${isSelected ? 'bg-brand-50' : 'hover:bg-gray-50'}`}>
                          <div className={`w-4 h-4 rounded border flex items-center justify-center transition ${isSelected ? 'bg-brand-600 border-brand-600' : 'border-gray-300'}`}>
                            {isSelected && <Check className="w-3 h-3 text-white" />}
                          </div>
                          <input type="checkbox" checked={isSelected} onChange={() => setSelectedTables((prev) => isSelected ? prev.filter((n) => n !== t.name) : [...prev, t.name])} className="sr-only" />
                          <span className="text-sm font-mono text-gray-700">{t.schema}.{t.name}</span>
                        </label>
                      );
                    }) : availableFiles.map((f) => {
                      const isSelected = selectedFiles.includes(f.name);
                      const ext = f.name.includes('.') ? f.name.split('.').pop()?.toLowerCase() : '';
                      const sizeStr = f.size != null ? (f.size > 1024 * 1024 ? `${(f.size / 1024 / 1024).toFixed(1)} MB` : `${(f.size / 1024).toFixed(1)} KB`) : '';
                      return (
                        <label key={f.name} className={`flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer transition ${isSelected ? 'bg-brand-50' : 'hover:bg-gray-50'}`}>
                          <div className={`w-4 h-4 rounded border flex items-center justify-center transition ${isSelected ? 'bg-brand-600 border-brand-600' : 'border-gray-300'}`}>
                            {isSelected && <Check className="w-3 h-3 text-white" />}
                          </div>
                          <input type="checkbox" checked={isSelected} onChange={() => setSelectedFiles((prev) => isSelected ? prev.filter((n) => n !== f.name) : [...prev, f.name])} className="sr-only" />
                          <div className="flex items-center gap-2 flex-1 min-w-0">
                            <span className="text-sm text-gray-700 truncate">{f.name}</span>
                            {f.container && <span className="text-[10px] text-gray-400">({f.container})</span>}
                          </div>
                          <div className="flex items-center gap-2 text-[10px] text-gray-400 whitespace-nowrap">
                            {ext && <span className="uppercase">{ext}</span>}
                            {sizeStr && <span>{sizeStr}</span>}
                          </div>
                        </label>
                      );
                    })}
                  </div>
                </>
              )}

              <div className="flex gap-3 justify-end mt-5 pt-4 border-t border-gray-100">
                <button onClick={() => setTablePickerConnector(null)} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition">Cancel</button>
                <button
                  onClick={handleStartIngestWithTables}
                  disabled={selected.length === 0 || loadingTables}
                  className="flex items-center gap-2 px-4 py-2 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 transition"
                >
                  <Download className="w-3.5 h-3.5" /> {actionLabel} {selected.length} {selected.length === 1 ? label.slice(0, -1) : label}
                </button>
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
}
