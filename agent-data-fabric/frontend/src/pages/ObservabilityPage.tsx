import React, { useEffect, useState } from 'react';
import { observabilityApi } from '../api/client';
import type { ObservabilitySummary, LLMCall } from '../types';
import { BarChart3, Loader2, Zap, Clock, Hash, Brain } from 'lucide-react';

export default function ObservabilityPage() {
  const [summary, setSummary] = useState<ObservabilitySummary | null>(null);
  const [calls, setCalls] = useState<LLMCall[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      observabilityApi.summary(),
      observabilityApi.llmCalls(),
    ]).then(([s, c]) => {
      setSummary(s.data);
      setCalls(c.data.items || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 text-brand-500 animate-spin" /></div>;

  const stats = summary ? [
    { label: 'Total Tokens', value: summary.tokens_total.toLocaleString(), icon: Hash, color: 'text-blue-600 bg-blue-50' },
    { label: 'Input Tokens', value: summary.tokens_input.toLocaleString(), icon: Zap, color: 'text-green-600 bg-green-50' },
    { label: 'Output Tokens', value: summary.tokens_output.toLocaleString(), icon: Zap, color: 'text-purple-600 bg-purple-50' },
    { label: 'Avg Latency', value: `${Math.round(summary.avg_latency_ms)}ms`, icon: Clock, color: 'text-orange-600 bg-orange-50' },
    { label: 'Total LLM Calls', value: summary.total_calls.toLocaleString(), icon: Brain, color: 'text-pink-600 bg-pink-50' },
  ] : [];

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-gray-900">Observability Dashboard</h2>
        <p className="text-sm text-gray-500">Monitor token usage, latency, and LLM performance</p>
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
        <div className="px-4 py-3 bg-gray-50 border-b">
          <h3 className="text-sm font-semibold text-gray-900">LLM Call History</h3>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase">Model</th>
              <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase">Input</th>
              <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase">Output</th>
              <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase">Latency</th>
              <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase">Time</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {calls.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">No LLM calls recorded</td></tr>
            ) : calls.map((c) => (
              <tr key={c.id} className="hover:bg-gray-50">
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
