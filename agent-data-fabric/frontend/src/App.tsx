import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAuthStore } from './store/authStore';
import AppShell from './components/layout/AppShell';
import LoginPage from './pages/LoginPage';
import ChatPage from './pages/ChatPage';
import ConnectorsPage from './pages/ConnectorsPage';
import MCPPage from './pages/MCPPage';
import ToolsPage from './pages/ToolsPage';
import SQLPage from './pages/SQLPage';
import CapabilitiesPage from './pages/CapabilitiesPage';
import ObservabilityPage from './pages/ObservabilityPage';
import SettingsPage from './pages/SettingsPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
});

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <ProtectedRoute>
                <AppShell />
              </ProtectedRoute>
            }
          >
            <Route path="/" element={<ChatPage />} />
            <Route path="/connectors" element={<ConnectorsPage />} />
            <Route path="/mcp" element={<MCPPage />} />
            <Route path="/tools" element={<ToolsPage />} />
            <Route path="/sql" element={<SQLPage />} />
            <Route path="/capabilities" element={<CapabilitiesPage />} />
            <Route path="/observability" element={<ObservabilityPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
