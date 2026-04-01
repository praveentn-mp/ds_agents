import React from 'react';
import { Settings } from 'lucide-react';

export default function SettingsPage() {
  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-gray-900">Settings</h2>
        <p className="text-sm text-gray-500">Application configuration and user management</p>
      </div>

      <div className="space-y-6">
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Application Info</h3>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between py-2 border-b border-gray-100">
              <span className="text-gray-500">App Name</span>
              <span className="text-gray-900 font-medium">Agentic Data Fabric</span>
            </div>
            <div className="flex justify-between py-2 border-b border-gray-100">
              <span className="text-gray-500">Version</span>
              <span className="text-gray-900 font-medium">1.0.0</span>
            </div>
            <div className="flex justify-between py-2 border-b border-gray-100">
              <span className="text-gray-500">Backend</span>
              <span className="text-gray-900 font-medium">http://localhost:7790</span>
            </div>
            <div className="flex justify-between py-2">
              <span className="text-gray-500">MCP Server</span>
              <span className="text-gray-900 font-medium">http://localhost:7792</span>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">RBAC Roles</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2 text-gray-500 font-medium">Permission</th>
                  <th className="text-center py-2 text-gray-500 font-medium">Admin</th>
                  <th className="text-center py-2 text-gray-500 font-medium">Developer</th>
                  <th className="text-center py-2 text-gray-500 font-medium">Analyst</th>
                  <th className="text-center py-2 text-gray-500 font-medium">Viewer</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {[
                  ['manage_users', true, false, false, false],
                  ['manage_connectors', true, true, false, false],
                  ['manage_mcp_servers', true, true, false, false],
                  ['manage_tools', true, true, false, false],
                  ['execute_sql_write', true, true, false, false],
                  ['execute_sql_read', true, true, true, false],
                  ['query_data', true, true, true, true],
                  ['view_traces', true, true, true, false],
                ].map(([perm, ...roles]) => (
                  <tr key={perm as string}>
                    <td className="py-2 text-gray-700 font-mono text-xs">{perm as string}</td>
                    {(roles as boolean[]).map((has, i) => (
                      <td key={i} className="py-2 text-center">
                        {has ? <span className="text-green-600">✓</span> : <span className="text-gray-300">—</span>}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
