"""MCP Registry — tracks servers, tools, resources across the system."""

from typing import Optional
from backend.mcp.client import MCPClient


class MCPRegistry:
    """Central registry for MCP servers and their capabilities."""

    _instance: Optional["MCPRegistry"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._servers = {}
            cls._instance._clients = {}
        return cls._instance

    def register_server(self, name: str, sse_url: str):
        self._servers[name] = {"sse_url": sse_url}
        self._clients[name] = MCPClient(sse_url)

    def unregister_server(self, name: str):
        self._servers.pop(name, None)
        client = self._clients.pop(name, None)
        if client:
            import asyncio
            try:
                asyncio.get_event_loop().create_task(client.close())
            except RuntimeError:
                pass

    def get_client(self, name: str) -> Optional[MCPClient]:
        return self._clients.get(name)

    def list_servers(self) -> dict:
        return dict(self._servers)


mcp_registry = MCPRegistry()
