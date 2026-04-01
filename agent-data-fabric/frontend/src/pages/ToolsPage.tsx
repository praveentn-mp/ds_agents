import React, { useEffect, useState } from 'react';
import { toolApi } from '../api/client';
import type { CustomTool } from '../types';
import { Wrench, Plus, Loader2, Play, Code2, RefreshCw, CheckCircle2, XCircle, Clock, X, Sparkles, Database, ChevronDown, ChevronUp, Save, Wand2 } from 'lucide-react';

interface ExecutionResult {
  success: boolean;
  result?: any;
  error?: string;
  duration_ms: number;
}

interface GeneratedTool {
  success: boolean;
  name?: string;
  description?: string;
  sql?: string;
  code?: string;
  input_schema?: Record<string, any>;
  explanation?: string;
  matched_tables?: string[];
  tokens_used?: { input: number; output: number };
  error?: string;
  raw_response?: string;
}

export default function ToolsPage() {
  const [tools, setTools] = useState<CustomTool[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [executing, setExecuting] = useState<Record<string, boolean>>({});
  const [results, setResults] = useState<Record<string, ExecutionResult>>({});
  const [expandedTool, setExpandedTool] = useState<string | null>(null);

  // Agent-assisted creation
  const [createMode, setCreateMode] = useState<'ai' | 'manual'>('ai');
  const [aiPrompt, setAiPrompt] = useState('');
  const [generating, setGenerating] = useState(false);
  const [generated, setGenerated] = useState<GeneratedTool | null>(null);

  // Manual / edit form
  const [form, setForm] = useState({ name: '', description: '', code: '', input_schema: '{}' });
  const [saving, setSaving] = useState(false);

  const fetchTools = async () => {
    setLoading(true);
    try { setTools((await toolApi.list()).data); } catch (err) { console.error(err); }
    setLoading(false);
  };

  useEffect(() => { fetchTools(); }, []);

  const handleGenerate = async () => {
    if (!aiPrompt.trim()) return;
    setGenerating(true);
    setGenerated(null);
    try {
      const res = await toolApi.generate(aiPrompt.trim());
      const data = res.data as GeneratedTool;
      setGenerated(data);
      if (data.success) {
        setForm({
          name: data.name || '',
          description: data.description || '',
          code: data.code || '',
          input_schema: JSON.stringify(data.input_schema || {}, null, 2),
        });
      }
    } catch (err: any) {
      setGenerated({ success: false, error: err.response?.data?.detail || 'Generation failed' });
    }
    setGenerating(false);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await toolApi.create({
        name: form.name,
        description: form.description,
        code: form.code,
        input_schema: JSON.parse(form.input_schema || '{}'),
      });
      setShowCreate(false);
      setGenerated(null);
      setAiPrompt('');
      setForm({ name: '', description: '', code: '', input_schema: '{}' });
      fetchTools();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to save tool');
    }
    setSaving(false);
  };

  const handleExecute = async (id: string) => {
    setExecuting((p) => ({ ...p, [id]: true }));
    setResults((p) => { const n = { ...p }; delete n[id]; return n; });
    try {
      const res = await toolApi.execute(id, {});
      setResults((p) => ({ ...p, [id]: res.data }));
    } catch (err: any) {
      setResults((p) => ({ ...p, [id]: { success: false, error: err.response?.data?.detail || 'Execution failed', duration_ms: 0 } }));
    }
    setExecuting((p) => ({ ...p, [id]: false }));
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Custom Tools</h2>
          <p className="text-sm text-gray-500">Build data tools with AI assistance or write your own code</p>
        </div>
        <div className="flex gap-2">
          <button onClick={fetchTools} className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 transition">
            <RefreshCw className="w-4 h-4" />
          </button>
          <button onClick={() => { setShowCreate(true); setCreateMode('ai'); setGenerated(null); setAiPrompt(''); }}
            className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 transition">
            <Plus className="w-4 h-4" /> Create Tool
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 text-brand-500 animate-spin" /></div>
      ) : tools.length === 0 && !showCreate ? (
        <div className="text-center py-20 bg-white rounded-xl border border-gray-200">
          <Wrench className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 mb-1">No custom tools created yet</p>
          <p className="text-xs text-gray-400 mb-4">Describe what you need and AI will generate a tool for you.</p>
          <button onClick={() => { setShowCreate(true); setCreateMode('ai'); }}
            className="inline-flex items-center gap-2 px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 transition">
            <Sparkles className="w-4 h-4" /> Create with AI
          </button>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {tools.map((t) => {
            const res = results[t.id];
            const isRunning = executing[t.id];
            const isExpanded = expandedTool === t.id;

            return (
              <div key={t.id} className="bg-white rounded-xl border border-gray-200 p-5">
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Code2 className="w-5 h-5 text-brand-500" />
                    <h3 className="font-semibold text-gray-900">{t.name}</h3>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-400">v{t.current_version}</span>
                    <button onClick={() => setExpandedTool(isExpanded ? null : t.id)}
                      className="p-1 text-gray-400 hover:text-gray-600 rounded">
                      {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                    </button>
                  </div>
                </div>
                <p className="text-sm text-gray-500 mb-3">{t.description || 'No description'}</p>

                {isExpanded && (
                  <pre className="text-xs bg-gray-50 rounded-lg p-3 font-mono text-gray-600 mb-3 overflow-x-auto max-h-40">{t.code}</pre>
                )}

                <div className="flex items-center gap-2">
                  <button onClick={() => handleExecute(t.id)} disabled={isRunning}
                    className="flex items-center gap-1 px-3 py-1.5 text-xs bg-green-50 text-green-700 rounded-lg hover:bg-green-100 disabled:opacity-50 transition">
                    {isRunning ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                    {isRunning ? 'Running...' : 'Execute'}
                  </button>
                  {res && (
                    <span className="flex items-center gap-1 text-xs text-gray-400">
                      <Clock className="w-3 h-3" /> {res.duration_ms}ms
                    </span>
                  )}
                </div>

                {res && (
                  <div className={`mt-3 rounded-lg border text-xs overflow-hidden ${res.success ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'}`}>
                    <div className="flex items-center justify-between px-3 py-1.5 border-b border-inherit">
                      <div className="flex items-center gap-1.5">
                        {res.success
                          ? <><CheckCircle2 className="w-3.5 h-3.5 text-green-600" /><span className="font-medium text-green-700">Success</span></>
                          : <><XCircle className="w-3.5 h-3.5 text-red-600" /><span className="font-medium text-red-700">Error</span></>}
                      </div>
                      <button onClick={() => setResults(p => { const n = {...p}; delete n[t.id]; return n; })}
                        className="p-0.5 text-gray-400 hover:text-gray-600 rounded transition"><X className="w-3 h-3" /></button>
                    </div>
                    <pre className="px-3 py-2 overflow-x-auto max-h-40 font-mono text-gray-700 whitespace-pre-wrap">
                      {res.success ? (typeof res.result === 'object' ? JSON.stringify(res.result, null, 2) : String(res.result)) : res.error}
                    </pre>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* ──── Create Tool Modal ──── */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setShowCreate(false)}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Create Custom Tool</h3>
              <button onClick={() => setShowCreate(false)} className="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100">
                <X className="w-4 h-4" /></button>
            </div>

            {/* Mode tabs */}
            <div className="flex gap-1 p-1 bg-gray-100 rounded-lg mb-4">
              <button onClick={() => setCreateMode('ai')}
                className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm rounded-md transition ${
                  createMode === 'ai' ? 'bg-white text-brand-700 shadow-sm font-medium' : 'text-gray-500 hover:text-gray-700'}`}>
                <Sparkles className="w-4 h-4" /> AI Generate
              </button>
              <button onClick={() => setCreateMode('manual')}
                className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm rounded-md transition ${
                  createMode === 'manual' ? 'bg-white text-brand-700 shadow-sm font-medium' : 'text-gray-500 hover:text-gray-700'}`}>
                <Code2 className="w-4 h-4" /> Manual
              </button>
            </div>

            {createMode === 'ai' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Describe what you want the tool to do</label>
                  <textarea value={aiPrompt} onChange={(e) => setAiPrompt(e.target.value)}
                    className="w-full px-3 py-2 border rounded-lg text-sm" rows={3}
                    placeholder="e.g., Get top wines by alcohol content, List companies by revenue, Calculate average deal value by industry..." />
                </div>
                <button onClick={handleGenerate} disabled={generating || !aiPrompt.trim()}
                  className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 disabled:opacity-50 transition">
                  {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wand2 className="w-4 h-4" />}
                  {generating ? 'Generating...' : 'Generate Tool'}
                </button>

                {generated && !generated.success && (
                  <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                    {generated.error || 'Generation failed'}
                  </div>
                )}

                {generated && generated.success && (
                  <div className="space-y-3">
                    {generated.matched_tables && generated.matched_tables.length > 0 && (
                      <div className="flex items-center gap-2 flex-wrap text-xs text-gray-500">
                        <Database className="w-3 h-3" /> Matched tables:
                        {generated.matched_tables.map((t) => (
                          <span key={t} className="px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded font-mono">{t}</span>
                        ))}
                      </div>
                    )}
                    {generated.explanation && (
                      <div className="p-3 bg-brand-50 border border-brand-200 rounded-lg text-sm text-brand-800">{generated.explanation}</div>
                    )}
                    {generated.sql && (
                      <div>
                        <label className="block text-xs font-medium text-gray-500 mb-1">Generated SQL</label>
                        <pre className="text-xs bg-gray-50 rounded-lg p-3 font-mono text-gray-600 overflow-x-auto max-h-32">{generated.sql}</pre>
                      </div>
                    )}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                      <input value={form.name} onChange={(e) => setForm({...form, name: e.target.value})}
                        className="w-full px-3 py-2 border rounded-lg text-sm" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                      <input value={form.description} onChange={(e) => setForm({...form, description: e.target.value})}
                        className="w-full px-3 py-2 border rounded-lg text-sm" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Code</label>
                      <textarea value={form.code} onChange={(e) => setForm({...form, code: e.target.value})}
                        className="w-full px-3 py-2 border rounded-lg text-sm font-mono" rows={6} />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Input Schema</label>
                      <textarea value={form.input_schema} onChange={(e) => setForm({...form, input_schema: e.target.value})}
                        className="w-full px-3 py-2 border rounded-lg text-sm font-mono" rows={3} />
                    </div>
                    <div className="flex gap-3 justify-end pt-2 border-t border-gray-100">
                      <button type="button" onClick={() => setShowCreate(false)}
                        className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition">Cancel</button>
                      <button onClick={handleSave} disabled={saving || !form.name}
                        className="flex items-center gap-2 px-4 py-2 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 transition">
                        {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                        Save Tool
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {createMode === 'manual' && (
              <form onSubmit={(e) => { e.preventDefault(); handleSave(); }} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                  <input value={form.name} onChange={(e) => setForm({...form, name: e.target.value})}
                    className="w-full px-3 py-2 border rounded-lg text-sm" required />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                  <input value={form.description} onChange={(e) => setForm({...form, description: e.target.value})}
                    className="w-full px-3 py-2 border rounded-lg text-sm" placeholder="What does this tool do?" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Code (Python)</label>
                  <textarea value={form.code} onChange={(e) => setForm({...form, code: e.target.value})}
                    className="w-full px-3 py-2 border rounded-lg text-sm font-mono" rows={6} required />
                  <p className="text-[10px] text-gray-400 mt-1">Use `arguments` dict for inputs, set `result` for output. Runs in a sandbox.</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Input Schema (JSON)</label>
                  <textarea value={form.input_schema} onChange={(e) => setForm({...form, input_schema: e.target.value})}
                    className="w-full px-3 py-2 border rounded-lg text-sm font-mono" rows={3} />
                </div>
                <div className="flex gap-3 justify-end pt-2 border-t border-gray-100">
                  <button type="button" onClick={() => setShowCreate(false)}
                    className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition">Cancel</button>
                  <button type="submit" disabled={saving}
                    className="flex items-center gap-2 px-4 py-2 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 transition">
                    {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                    Create
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
