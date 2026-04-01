import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';
import {
  MessageSquare,
  Database,
  Server,
  Search,
  Wrench,
  BarChart3,
  Settings,
  Eye,
  LogOut,
  Layers,
  Radar,
} from 'lucide-react';

const navItems = [
  { path: '/', label: 'Chat', icon: MessageSquare },
  { path: '/connectors', label: 'Data Sources', icon: Database },
  { path: '/sql', label: 'SQL Explorer', icon: Search },
  { path: '/search', label: 'Search', icon: Radar },
  { path: '/tools', label: 'Tools', icon: Wrench },
  { path: '/mcp', label: 'MCP Inspector', icon: Server },
  { path: '/capabilities', label: 'Capabilities', icon: Layers },
  { path: '/observability', label: 'Observability', icon: BarChart3 },
  { path: '/settings', label: 'Settings', icon: Settings },
];

export default function Sidebar() {
  const location = useLocation();
  const { user, logout } = useAuthStore();

  return (
    <aside className="flex flex-col w-64 bg-white border-r border-gray-200 h-screen">
      {/* Logo */}
      <div className="flex items-center gap-3 px-6 py-5 border-b border-gray-100">
        <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center">
          <Layers className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-sm font-semibold text-gray-900">Agent Data Fabric</h1>
          <p className="text-[10px] text-gray-400 uppercase tracking-wider">MCP Platform</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {navItems.map(({ path, label, icon: Icon }) => {
          const isActive = location.pathname === path;
          return (
            <Link
              key={path}
              to={path}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all ${
                isActive
                  ? 'bg-brand-50 text-brand-700 font-medium'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              }`}
            >
              <Icon className={`w-4 h-4 ${isActive ? 'text-brand-600' : 'text-gray-400'}`} />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* User */}
      <div className="px-3 py-4 border-t border-gray-100">
        <div className="flex items-center gap-3 px-3 py-2">
          <div className="w-8 h-8 rounded-full bg-brand-100 flex items-center justify-center">
            <span className="text-xs font-medium text-brand-700">
              {user?.full_name?.charAt(0) || user?.email?.charAt(0) || 'U'}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900 truncate">{user?.full_name || user?.email}</p>
            <p className="text-xs text-gray-400">{user?.role_name || 'User'}</p>
          </div>
          <button onClick={logout} className="p-1 text-gray-400 hover:text-gray-600 transition-colors">
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
