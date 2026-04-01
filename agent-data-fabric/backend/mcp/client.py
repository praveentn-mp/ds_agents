"""MCP client wrapper."""

import httpx
import logging
from typing import Optional

logger = logging.getLogger("adf.mcp_client")


class MCPClient:
    """Client for communicating with MCP servers via SSE."""

    def __init__(self, sse_url: str):
        self.sse_url = sse_url
        self._client = httpx.AsyncClient(timeout=30.0)

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call a tool on the MCP server."""
        try:
            response = await self._client.post(
                self.sse_url.replace("/sse", "/tools/call"),
                json={"name": tool_name, "arguments": arguments},
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"MCP tool call failed: {e}")
            return {"error": str(e)}

    async def list_tools(self) -> list[dict]:
        """List available tools on the MCP server."""
        try:
            response = await self._client.get(
                self.sse_url.replace("/sse", "/tools/list"),
            )
            response.raise_for_status()
            return response.json().get("tools", [])
        except Exception as e:
            logger.error(f"MCP list tools failed: {e}")
            return []

    async def list_resources(self) -> list[dict]:
        """List available resources on the MCP server."""
        try:
            response = await self._client.get(
                self.sse_url.replace("/sse", "/resources/list"),
            )
            response.raise_for_status()
            return response.json().get("resources", [])
        except Exception as e:
            logger.error(f"MCP list resources failed: {e}")
            return []

    async def close(self):
        await self._client.aclose()
