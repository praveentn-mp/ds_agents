import React, { useState } from 'react';
import { searchApi, connectorApi } from '../api/client';
import { Search, Loader2, Database, Columns3, Hash, FileText, SlidersHorizontal } from 'lucide-react';

interface SearchResult {
  index_type: string;
  score: number;
  table_name?: string;
  column_name?: string;
  description?: string;
  value_text?: string;
  data_type?: string;
  source_file?: string;
  chunk_text?: string;
  connector_id?: string;
  metadata?: Record<string, any>;
}

interface SearchResponse {
  query: string;
  total_results: number;
  table_matches: SearchResult[];
  column_matches: SearchResult[];
  value_matches: SearchResult[];
  chunk_matches: SearchResult[];
}

function ScoreBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = pct >= 80 ? 'bg-green-100 text-green-700' : pct >= 50 ? 'bg-amber-100 text-amber-700' : 'bg-gray-100 text-gray-600';
  return <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${color}`}>{pct}%</span>;
}

function ResultSection({ title, icon: Icon, results, color }: {
  title: string; icon: React.ElementType; results: SearchResult[]; color: string;
}) {
  if (!results || results.length === 0) return null;
  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div className={`flex items-center gap-2 px-4 py-3 border-b border-gray-100 ${color}`}>
        <Icon className="w-4 h-4" />
        <span className="text-sm font-semibold">{title}</span>
        <span className="ml-auto text-xs opacity-60">{results.length} result{results.length !== 1 ? 's' : ''}</span>
      </div>
      <div className="divide-y divide-gray-50">
        {results.map((r, i) => (
          <div key={i} className="px-4 py-3 hover:bg-gray-50 transition">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                {r.index_type === 'table' && (
                  <>
                    <span className="font-mono text-sm font-medium text-gray-900">{r.table_name}</span>
                    {r.description && <p className="text-xs text-gray-500 mt-0.5">{r.description}</p>}
                  </>
                )}
                {r.index_type === 'column' && (
                  <>
                    <span className="font-mono text-sm text-gray-900">
                      <span className="text-gray-400">{r.table_name}.</span>{r.column_name}
                    </span>
                    {r.description && <p className="text-xs text-gray-500 mt-0.5">{r.description}</p>}
                    {r.data_type && (
                      <span className="text-[10px] text-gray-400 mt-0.5 block">Type: {r.data_type}</span>
                    )}
                  </>
                )}
                {r.index_type === 'value' && (
                  <>
                    <span className="font-mono text-sm text-gray-900">{r.value_text}</span>
                    <p className="text-xs text-gray-400 mt-0.5">
                      in <span className="font-mono">{r.table_name}.{r.column_name}</span>
                    </p>
                  </>
                )}
                {r.index_type === 'chunk' && (
                  <>
                    <p className="text-sm text-gray-900 line-clamp-3">{r.chunk_text}</p>
                    {r.source_file && (
                      <p className="text-xs text-gray-400 mt-1">Source: {r.source_file}</p>
                    )}
                  </>
                )}
              </div>
              <ScoreBadge score={r.score} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Filters
  const [topK, setTopK] = useState(20);
  const [minScore, setMinScore] = useState(0.25);
  const [connectorId, setConnectorId] = useState('');
  const [showFilters, setShowFilters] = useState(false);

  // Connector list for filter
  const [connectors, setConnectors] = useState<{ id: string; name: string }[]>([]);
  const [connectorsLoaded, setConnectorsLoaded] = useState(false);

  const loadConnectors = async () => {
    if (connectorsLoaded) return;
    try {
      const res = await connectorApi.list();
      setConnectors(res.data.map((c: any) => ({ id: c.id, name: c.name })));
    } catch {}
    setConnectorsLoaded(true);
  };

  const handleSearch = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError('');
    setResults(null);
    try {
      const res = await searchApi.search(query, {
        top_k: topK,
        min_score: minScore,
        connector_id: connectorId || undefined,
      });
      setResults(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Search failed');
    }
    setLoading(false);
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-gray-900">Hybrid Search</h2>
        <p className="text-sm text-gray-500">Search across all indexed data — tables, columns, values, and documents</p>
      </div>

      {/* Search bar */}
      <form onSubmit={handleSearch} className="mb-6">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search tables, columns, values, documents..."
              className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          <button
            type="button"
            onClick={() => { setShowFilters(!showFilters); loadConnectors(); }}
            className={`px-3 py-2.5 border rounded-lg transition ${showFilters ? 'border-brand-300 bg-brand-50 text-brand-700' : 'border-gray-200 text-gray-500 hover:bg-gray-50'}`}
          >
            <SlidersHorizontal className="w-4 h-4" />
          </button>
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="px-5 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 disabled:opacity-50 transition"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Search'}
          </button>
        </div>

        {/* Filters */}
        {showFilters && (
          <div className="mt-3 flex gap-4 items-end bg-gray-50 rounded-lg p-3 border border-gray-100">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Min Score</label>
              <div className="flex items-center gap-2">
                <input
                  type="range"
                  min="0" max="1" step="0.05"
                  value={minScore}
                  onChange={(e) => setMinScore(parseFloat(e.target.value))}
                  className="w-28 accent-brand-600"
                />
                <span className="text-xs font-mono text-gray-600 w-8">{minScore}</span>
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Top K</label>
              <input
                type="number"
                min="1" max="100"
                value={topK}
                onChange={(e) => setTopK(parseInt(e.target.value) || 20)}
                className="w-20 px-2 py-1 border border-gray-200 rounded text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Connector</label>
              <select
                value={connectorId}
                onChange={(e) => setConnectorId(e.target.value)}
                className="px-2 py-1 border border-gray-200 rounded text-sm min-w-[140px]"
              >
                <option value="">All Connectors</option>
                {connectors.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
          </div>
        )}
      </form>

      {/* Error */}
      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">{error}</div>
      )}

      {/* Results */}
      {results && (
        <div className="space-y-4">
          <p className="text-sm text-gray-500">
            Found <span className="font-semibold text-gray-700">{results.total_results}</span> results for "<span className="font-medium">{results.query}</span>"
          </p>

          <ResultSection title="Tables" icon={Database} results={results.table_matches} color="bg-blue-50 text-blue-700" />
          <ResultSection title="Columns" icon={Columns3} results={results.column_matches} color="bg-purple-50 text-purple-700" />
          <ResultSection title="Values" icon={Hash} results={results.value_matches} color="bg-amber-50 text-amber-700" />
          <ResultSection title="Document Chunks" icon={FileText} results={results.chunk_matches} color="bg-green-50 text-green-700" />

          {results.total_results === 0 && (
            <div className="text-center py-16 bg-white rounded-xl border border-gray-200">
              <Search className="w-10 h-10 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500">No results found</p>
              <p className="text-xs text-gray-400 mt-1">Try adjusting your query or lowering the minimum score</p>
            </div>
          )}
        </div>
      )}

      {/* Empty state */}
      {!results && !loading && (
        <div className="text-center py-20 bg-white rounded-xl border border-gray-200">
          <Search className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 mb-1">Search across your indexed data</p>
          <p className="text-xs text-gray-400">Enter a query to find matching tables, columns, values, and documents using hybrid vector search</p>
        </div>
      )}
    </div>
  );
}
