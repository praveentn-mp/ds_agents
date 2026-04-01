import React, { useEffect, useState } from 'react';
import { mcpApi } from '../api/client';
import type { MCPServer, MCPResource, MCPTool, MCPPrompt } from '../types';
import { Server, FileText, Wrench, Brain, Play, Square, RefreshCw, Loader2, ExternalLink } from 'lucide-react';

type Tab = 'servers' | 'resources' | 'tools' | 'prompts';

export default function MCPPage() {
  const [tab, setTab] = useState<Tab>('servers');
  const [servers, setServers] = useState<MCPServer[]>([]);
  const [resources, setResources] = useState<MCPResource[]>([]);
  const [tools, setTools] = useState<MCPTool[]>([]);
  const [prompts, setPrompts] = useState<MCPPrompt[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [s, r, t, p] = await Promise.all([
        mcpApi.listServers(),
        mcpApi.listResources(),
        mcpApi.listTools(),
        mcpApi.listPrompts(),
      ]);
      setServers(s.data);
      setResources(r.data);
      setTools(t.data);
      setPrompts(p.data);
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, []);

  const handleStartServer = async (id: string) => {
    try {
      await mcpApi.startServer(id);
      fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to start server');
    }
  };

  const handleStopServer = async (id: string) => {
    try {
      await mcpApi.stopServer(id);
      fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to stop server');
    }
  };

  const tabs = [
    { key: 'servers' as Tab, label: 'Servers', icon: Server, count: servers.length },
    { key: 'resources' as Tab, label: 'Resources', icon: FileText, count: resources.length },
    { key: 'tools' as Tab, label: 'Tools', icon: Wrench, count: tools.length },
    { key: 'prompts' as Tab, label: 'Prompts', icon: Brain, count: prompts.length },
  ];

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-gray-900">MCP Inspector</h2>
          <p className="text-sm text-gray-500">Inspect and manage MCP servers, resources, tools, and prompts</p>
        </div>
        <div className="flex gap-2">
          <a
            href="http://localhost:6274"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-brand-600 rounded-lg hover:bg-brand-700 transition"
          >
            <ExternalLink className="w-4 h-4" />
            Open MCP Inspector
          </a>
          <button onClick={fetchData} className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 transition">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 rounded-xl p-1 mb-6">
        {tabs.map(({ key, label, icon: Icon, count }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition flex-1 justify-center ${
              tab === key ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <Icon className="w-4 h-4" />
            {label}
            <span className="text-xs bg-gray-200 text-gray-600 px-1.5 py-0.5 rounded-full">{count}</span>
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 text-brand-500 animate-spin" /></div>
      ) : (
        <>
          {tab === 'servers' && (
            <div className="grid gap-4 md:grid-cols-2">
              {servers.length === 0 ? (
                <p className="text-sm text-gray-400 col-span-2 text-center py-12">No MCP servers registered</p>
              ) : servers.map((s) => (
                <div key={s.id} className="bg-white rounded-xl border border-gray-200 p-5">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <h3 className="font-semibold text-gray-900">{s.name}</h3>
                      <p className="text-xs text-gray-400">{s.image || 'Custom server'}</p>
                    </div>
                    <span className={`px-2 py-0.5 text-xs rounded-full ${s.status === 'running' ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                      {s.status}
                    </span>
                  </div>
                  {s.sse_url && <p className="text-xs text-gray-400 font-mono mb-2">{s.sse_url}</p>}
                  <p className="text-xs text-gray-400 mb-3">Tools: {s.tool_count}</p>
                  <div className="flex gap-2">
                    {s.status !== 'running' ? (
                      <button onClick={() => handleStartServer(s.id)} className="flex items-center gap-1 px-3 py-1.5 text-xs bg-green-50 text-green-700 rounded-lg hover:bg-green-100 transition">
                        <Play className="w-3 h-3" /> Start
                      </button>
                    ) : (
                      <button onClick={() => handleStopServer(s.id)} className="flex items-center gap-1 px-3 py-1.5 text-xs bg-red-50 text-red-700 rounded-lg hover:bg-red-100 transition">
                        <Square className="w-3 h-3" /> Stop
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {tab === 'resources' && (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">URI</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Name</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Type</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Source</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {resources.length === 0 ? (
                    <tr><td colSpan={4} className="px-4 py-8 text-center text-gray-400">No resources registered</td></tr>
                  ) : resources.map((r) => (
                    <tr key={r.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-mono text-xs text-brand-600">{r.uri}</td>
                      <td className="px-4 py-3">{r.name}</td>
                      <td className="px-4 py-3 text-xs text-gray-500">{r.resource_type}</td>
                      <td className="px-4 py-3 text-xs text-gray-500">{r.source_type}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {tab === 'tools' && (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {tools.length === 0 ? (
                <p className="text-sm text-gray-400 col-span-3 text-center py-12">No tools registered</p>
              ) : tools.map((t) => (
                <div key={t.id} className="bg-white rounded-xl border border-gray-200 p-5">
                  <h3 className="font-semibold text-gray-900 mb-1">{t.name}</h3>
                  <p className="text-xs text-gray-500 mb-2">{t.description || 'No description'}</p>
                  <div className="flex gap-2 text-xs">
                    <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full">{t.source_type}</span>
                    {t.server_name && <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full">{t.server_name}</span>}
                  </div>
                </div>
              ))}
            </div>
          )}

          {tab === 'prompts' && (
            <div className="space-y-4">
              {prompts.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-12">No prompts registered</p>
              ) : prompts.map((p) => (
                <div key={p.id} className="bg-white rounded-xl border border-gray-200 p-5">
                  <h3 className="font-semibold text-gray-900 mb-1">{p.name}</h3>
                  <p className="text-xs text-gray-500 mb-3">{p.description || 'No description'}</p>
                  <pre className="text-xs bg-gray-50 rounded-lg p-3 overflow-x-auto font-mono text-gray-600">{p.template}</pre>
                  {p.variables && p.variables.length > 0 && (
                    <div className="flex gap-2 mt-3">
                      {p.variables.map((v: string) => (
                        <span key={v} className="px-2 py-0.5 text-xs bg-purple-50 text-purple-700 rounded-full">
                          {`{{${v}}}`}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
