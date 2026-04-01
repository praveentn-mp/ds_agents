import React, { useEffect, useState } from 'react';
import { capabilitiesApi } from '../api/client';
import type { Capabilities } from '../types';
import { Layers, Database, Wrench, Brain, Loader2, ArrowRight } from 'lucide-react';

const TOOL_CONTEXT: Record<string, string> = {
  QueryResource: 'Queries data from any connected database via SQL. Works with PostgreSQL connectors.',
  WriteResource: 'Writes data to connected sources (databases, blob storage, filesystem).',
  MCPToolCall: 'Calls any registered MCP server tool — file operations, web search, Slack, GitHub, etc.',
  mcp_query: 'Executes SQL queries against connected PostgreSQL databases and returns results.',
  mcp_write: 'Writes data to any connected source (database table, blob, file).',
  mcp_discover: 'Discovers schema (tables, columns, containers) from any connected data source.',
  mcp_tool_proxy: 'Proxies calls to MCP server tools running in Docker containers.',
  mcp_rag_search: 'Semantic search over documents indexed into the vector store (RAG).',
};

export default function CapabilitiesPage() {
  const [caps, setCaps] = useState<Capabilities | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    capabilitiesApi.list().then((res) => {
      setCaps(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 text-brand-500 animate-spin" /></div>;
  if (!caps) return <p className="p-6 text-gray-500">Failed to load capabilities</p>;

  const sections = [
    { title: 'Data Connectors', icon: Database, items: caps.connectors, color: 'green' },
    { title: 'MCP Tools', icon: Wrench, items: caps.mcp_tools, color: 'blue' },
    { title: 'Custom Tools', icon: Wrench, items: caps.custom_tools, color: 'purple' },
    { title: 'Prompts', icon: Brain, items: caps.prompts, color: 'orange' },
  ];

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-gray-900">Capability Explorer</h2>
        <p className="text-sm text-gray-500">Everything the agent can access — data sources, tools, and prompts</p>
      </div>

      {/* How it works banner */}
      <div className="mb-6 bg-brand-50 border border-brand-200 rounded-xl p-4">
        <div className="flex items-center gap-6 text-sm text-brand-700">
          <div className="flex items-center gap-1.5">
            <Database className="w-4 h-4" />
            <span className="font-medium">Data Sources</span>
          </div>
          <ArrowRight className="w-4 h-4 text-brand-400" />
          <div className="flex items-center gap-1.5">
            <Wrench className="w-4 h-4" />
            <span className="font-medium">Tools</span>
          </div>
          <ArrowRight className="w-4 h-4 text-brand-400" />
          <div className="flex items-center gap-1.5">
            <Brain className="w-4 h-4" />
            <span className="font-medium">Agent Intelligence</span>
          </div>
        </div>
        <p className="text-xs text-brand-600 mt-1.5">
          The agent uses tools to read from and write to data sources. Prompts guide how it responds. Everything is auto-discovered.
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {sections.map(({ title, icon: Icon, items, color }) => (
          <div key={title} className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-center gap-2 mb-4">
              <Icon className="w-5 h-5 text-gray-500" />
              <h3 className="font-semibold text-gray-900">{title}</h3>
              <span className="ml-auto text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{items.length}</span>
            </div>
            {items.length === 0 ? (
              <p className="text-sm text-gray-400">None registered</p>
            ) : (
              <div className="space-y-2">
                {items.map((item: any) => (
                  <div key={item.id} className="flex items-center gap-3 px-3 py-2 bg-gray-50 rounded-lg">
                    <div className="flex-1">
                      <p className="text-sm font-medium text-gray-900">{item.name}</p>
                      <p className="text-xs text-gray-500">
                        {TOOL_CONTEXT[item.name] || item.description || item.type || item.source || 'No description'}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
