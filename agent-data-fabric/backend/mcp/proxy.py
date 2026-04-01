"""MCP Tool Proxy — routes MCPToolCall to the appropriate server."""

from backend.mcp.registry import mcp_registry


async def proxy_tool_call(server_name: str, tool_name: str, arguments: dict) -> dict:
    """Proxy a tool call to the appropriate MCP server."""
    client = mcp_registry.get_client(server_name)
    if not client:
        return {"error": f"MCP server '{server_name}' not found or not running"}
    return await client.call_tool(tool_name, arguments)
