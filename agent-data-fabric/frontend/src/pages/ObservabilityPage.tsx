import React, { useEffect, useState, useCallback } from 'react';
import { observabilityApi } from '../api/client';
import type { LLMCall } from '../types';
import { BarChart3, Loader2, Zap, Clock, Hash, Brain, Filter } from 'lucide-react';

interface SummaryData {
  tokens_total: number;
  tokens_input: number;
  tokens_output: number;
  tokens_cache: number;
  avg_latency_ms: number;
  total_calls: number;
  top_models: { model: string; count: number }[];
  categories?: { category: string; count: number; tokens: number }[];
}

const CATEGORY_COLORS: Record<string, string> = {
  agent: 'bg-blue-100 text-blue-700',
  ingestion: 'bg-amber-100 text-amber-700',
  tool: 'bg-purple-100 text-purple-700',
  unknown: 'bg-gray-100 text-gray-600',
};

function CategoryBadge({ category }: { category: string | null }) {
  const cat = category || 'unknown';
  const color = CATEGORY_COLORS[cat] || CATEGORY_COLORS.unknown;
  return <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${color}`}>{cat}</span>;
}

export default function ObservabilityPage() {
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [calls, setCalls] = useState<LLMCall[]>([]);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState<string>('');

  const loadData = useCallback(async (cat?: string) => {
    setLoading(true);
    try {
      const [s, c] = await Promise.all([
        observabilityApi.summary(cat || undefined),
        observabilityApi.llmCalls(1, 50, cat || undefined),
      ]);
      setSummary(s.data);
      setCalls(c.data.items || []);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleCategoryChange = (cat: string) => {
    setCategoryFilter(cat);
    loadData(cat || undefined);
  };

  if (loading && !summary) return <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 text-brand-500 animate-spin" /></div>;

  const stats = summary ? [
    { label: 'Total Tokens', value: summary.tokens_total.toLocaleString(), icon: Hash, color: 'text-blue-600 bg-blue-50' },
    { label: 'Input Tokens', value: summary.tokens_input.toLocaleString(), icon: Zap, color: 'text-green-600 bg-green-50' },
    { label: 'Output Tokens', value: summary.tokens_output.toLocaleString(), icon: Zap, color: 'text-purple-600 bg-purple-50' },
    { label: 'Avg Latency', value: `${Math.round(summary.avg_latency_ms)}ms`, icon: Clock, color: 'text-orange-600 bg-orange-50' },
    { label: 'Total LLM Calls', value: summary.total_calls.toLocaleString(), icon: Brain, color: 'text-pink-600 bg-pink-50' },
  ] : [];

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Observability Dashboard</h2>
          <p className="text-sm text-gray-500">Monitor token usage, latency, and LLM performance</p>
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-400" />
          <select
            value={categoryFilter}
            onChange={(e) => handleCategoryChange(e.target.value)}
            className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="">All Categories</option>
            <option value="agent">Agent</option>
            <option value="ingestion">Ingestion</option>
            <option value="tool">Tool</option>
          </select>
        </div>
      </div>

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-5 mb-6">
        {stats.map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-4">
            <div className={`w-8 h-8 rounded-lg ${color} flex items-center justify-center mb-3`}>
              <Icon className="w-4 h-4" />
            </div>
            <p className="text-2xl font-bold text-gray-900">{value}</p>
            <p className="text-xs text-gray-500 mt-1">{label}</p>
          </div>
        ))}
      </div>

      {/* Category breakdown */}
      {summary && summary.categories && summary.categories.length > 0 && !categoryFilter && (
        <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">Usage by Category</h3>
          <div className="grid gap-3 md:grid-cols-4">
            {summary.categories.map((cat) => (
              <button
                key={cat.category}
                onClick={() => handleCategoryChange(cat.category)}
                className="text-left p-3 rounded-lg border border-gray-100 hover:border-brand-200 hover:bg-brand-50 transition"
              >
                <div className="flex items-center gap-2 mb-1">
                  <CategoryBadge category={cat.category} />
                </div>
                <p className="text-lg font-bold text-gray-900">{cat.count.toLocaleString()} <span className="text-xs font-normal text-gray-400">calls</span></p>
                <p className="text-xs text-gray-500">{cat.tokens.toLocaleString()} tokens</p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Top models */}
      {summary && summary.top_models.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">Top Models</h3>
          <div className="space-y-2">
            {summary.top_models.map((m) => (
              <div key={m.model} className="flex items-center gap-3">
                <span className="text-sm text-gray-700 w-40">{m.model}</span>
                <div className="flex-1 bg-gray-100 rounded-full h-2">
                  <div className="bg-brand-500 h-2 rounded-full" style={{ width: `${(m.count / summary.total_calls) * 100}%` }} />
                </div>
                <span className="text-xs text-gray-500 w-12 text-right">{m.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* LLM Call History */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-4 py-3 bg-gray-50 border-b flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-900">LLM Call History</h3>
          {categoryFilter && (
            <button onClick={() => handleCategoryChange('')} className="text-xs text-brand-600 hover:text-brand-700 font-medium">
              Clear filter
            </button>
          )}
        </div>
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase">Category</th>
              <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase">Model</th>
              <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase">Input</th>
              <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase">Output</th>
              <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase">Latency</th>
              <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase">Time</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {calls.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">No LLM calls recorded</td></tr>
            ) : calls.map((c) => (
              <tr key={c.id} className="hover:bg-gray-50">
                <td className="px-4 py-2"><CategoryBadge category={c.category} /></td>
                <td className="px-4 py-2 text-xs font-mono">{c.model}</td>
                <td className="px-4 py-2 text-xs">{c.tokens_input.toLocaleString()}</td>
                <td className="px-4 py-2 text-xs">{c.tokens_output.toLocaleString()}</td>
                <td className="px-4 py-2 text-xs">{c.latency_ms}ms</td>
                <td className="px-4 py-2 text-xs text-gray-500">{new Date(c.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
