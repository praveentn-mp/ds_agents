import React, { useEffect, useState } from 'react';
import { toolApi } from '../api/client';
import type { CustomTool } from '../types';
import { Wrench, Plus, Loader2, Play, Code2, RefreshCw, CheckCircle2, XCircle, Clock, X } from 'lucide-react';

interface ExecutionResult {
  success: boolean;
  result?: any;
  error?: string;
  duration_ms: number;
}

export default function ToolsPage() {
  const [tools, setTools] = useState<CustomTool[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [executing, setExecuting] = useState<Record<string, boolean>>({});
  const [results, setResults] = useState<Record<string, ExecutionResult>>({});
  const [form, setForm] = useState({ name: '', description: '', code: 'result = arguments.get("input", "hello")', input_schema: '{}' });

  const fetchTools = async () => {
    setLoading(true);
    try { setTools((await toolApi.list()).data); } catch (err) { console.error(err); }
    setLoading(false);
  };

  useEffect(() => { fetchTools(); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await toolApi.create({ ...form, input_schema: JSON.parse(form.input_schema) });
      setShowCreate(false);
      setForm({ name: '', description: '', code: 'result = arguments.get("input", "hello")', input_schema: '{}' });
      fetchTools();
    } catch (err: any) {
      setResults((p) => ({ ...p, __create__: { success: false, error: err.response?.data?.detail || 'Failed', duration_ms: 0 } }));
    }
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

  const clearResult = (id: string) => {
    setResults((p) => { const n = { ...p }; delete n[id]; return n; });
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Custom Tools</h2>
          <p className="text-sm text-gray-500">Build, manage, and execute sandboxed Python tools</p>
        </div>
        <div className="flex gap-2">
          <button onClick={fetchTools} className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 transition">
            <RefreshCw className="w-4 h-4" />
          </button>
          <button onClick={() => setShowCreate(true)} className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 transition">
            <Plus className="w-4 h-4" /> Create Tool
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 text-brand-500 animate-spin" /></div>
      ) : tools.length === 0 ? (
        <div className="text-center py-20 bg-white rounded-xl border border-gray-200">
          <Wrench className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 mb-1">No custom tools created yet</p>
          <p className="text-xs text-gray-400">Tools are sandboxed Python functions the agent can call on your behalf.</p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {tools.map((t) => {
            const res = results[t.id];
            const isRunning = executing[t.id];

            return (
              <div key={t.id} className="bg-white rounded-xl border border-gray-200 p-5">
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Code2 className="w-5 h-5 text-brand-500" />
                    <h3 className="font-semibold text-gray-900">{t.name}</h3>
                  </div>
                  <span className="text-xs text-gray-400">v{t.current_version}</span>
                </div>
                <p className="text-sm text-gray-500 mb-3">{t.description || 'No description'}</p>
                <pre className="text-xs bg-gray-50 rounded-lg p-3 font-mono text-gray-600 mb-3 overflow-x-auto max-h-32">{t.code}</pre>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleExecute(t.id)}
                    disabled={isRunning}
                    className="flex items-center gap-1 px-3 py-1.5 text-xs bg-green-50 text-green-700 rounded-lg hover:bg-green-100 disabled:opacity-50 transition"
                  >
                    {isRunning ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                    {isRunning ? 'Running...' : 'Execute'}
                  </button>
                  {res && (
                    <span className="flex items-center gap-1 text-xs text-gray-400">
                      <Clock className="w-3 h-3" /> {res.duration_ms}ms
                    </span>
                  )}
                </div>

                {/* Inline result display */}
                {res && (
                  <div className={`mt-3 rounded-lg border text-xs overflow-hidden ${
                    res.success ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'
                  }`}>
                    <div className="flex items-center justify-between px-3 py-1.5 border-b border-inherit">
                      <div className="flex items-center gap-1.5">
                        {res.success ? (
                          <><CheckCircle2 className="w-3.5 h-3.5 text-green-600" /><span className="font-medium text-green-700">Success</span></>
                        ) : (
                          <><XCircle className="w-3.5 h-3.5 text-red-600" /><span className="font-medium text-red-700">Error</span></>
                        )}
                      </div>
                      <button onClick={() => clearResult(t.id)} className="p-0.5 text-gray-400 hover:text-gray-600 rounded transition">
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                    <pre className="px-3 py-2 overflow-x-auto max-h-40 font-mono text-gray-700 whitespace-pre-wrap">
                      {res.success
                        ? (typeof res.result === 'object' ? JSON.stringify(res.result, null, 2) : String(res.result))
                        : res.error}
                    </pre>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {showCreate && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setShowCreate(false)}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Create Custom Tool</h3>
              <button onClick={() => setShowCreate(false)} className="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100"><X className="w-4 h-4" /></button>
            </div>
            {results.__create__?.error && (
              <div className="mb-3 px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">{results.__create__.error}</div>
            )}
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                <input value={form.name} onChange={(e) => setForm({...form, name: e.target.value})} className="w-full px-3 py-2 border rounded-lg text-sm" required />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <input value={form.description} onChange={(e) => setForm({...form, description: e.target.value})} className="w-full px-3 py-2 border rounded-lg text-sm" placeholder="What does this tool do?" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Code (Python)</label>
                <textarea value={form.code} onChange={(e) => setForm({...form, code: e.target.value})} className="w-full px-3 py-2 border rounded-lg text-sm font-mono" rows={6} required />
                <p className="text-[10px] text-gray-400 mt-1">Use `arguments` dict for inputs, set `result` for output. Runs in a sandbox.</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Input Schema (JSON)</label>
                <textarea value={form.input_schema} onChange={(e) => setForm({...form, input_schema: e.target.value})} className="w-full px-3 py-2 border rounded-lg text-sm font-mono" rows={3} />
              </div>
              <div className="flex gap-3 justify-end pt-2 border-t border-gray-100">
                <button type="button" onClick={() => setShowCreate(false)} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition">Cancel</button>
                <button type="submit" className="px-4 py-2 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700 transition">Create</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
