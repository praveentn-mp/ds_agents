"""MCP Server — FastMCP standalone process with SSE transport."""

import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("adf.mcp_server")

mcp = FastMCP(
    "Agentic Data Fabric MCP Server",
    instructions="Central MCP server for the Agentic Data Fabric platform",
)


# ─── Resources ───────────────────────────────────────────────────────────────

@mcp.resource("connector://info")
def connector_info() -> str:
    """Get information about available connectors."""
    return "Agentic Data Fabric supports: PostgreSQL, Azure Blob Storage, Filesystem connectors. Use the backend API to manage connectors."


@mcp.resource("mcp://info")
def mcp_info() -> str:
    """Get information about the MCP server."""
    return "This is the central MCP server for Agentic Data Fabric. It provides tools for querying data, writing data, and calling external MCP server tools."


# ─── Tools ────────────────────────────────────────────────────────────────────

@mcp.tool()
async def query_resource(resource_uri: str, query: str) -> str:
    """Query a data resource using natural language or SQL.

    Args:
        resource_uri: The URI of the resource to query (e.g., connector://postgres/customers)
        query: The query to execute (SQL or natural language)
    """
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{os.environ.get('BACKEND_URL', 'http://localhost:7790')}/sql/execute",
                json={"query": query, "resource_uri": resource_uri},
                timeout=30.0,
            )
            return response.text
    except Exception as e:
        return f"Query failed: {str(e)}"


@mcp.tool()
async def write_resource(resource_uri: str, payload: dict) -> str:
    """Write data to a resource.

    Args:
        resource_uri: The URI of the resource to write to
        payload: The data to write
    """
    return f"Write to {resource_uri}: payload received with {len(payload)} fields. (Backend integration pending)"


@mcp.tool()
async def mcp_tool_call(server: str, tool: str, arguments: dict) -> str:
    """Call a tool on any running Docker MCP server.

    Args:
        server: Name of the MCP server
        tool: Name of the tool to call
        arguments: Arguments to pass to the tool
    """
    import httpx
    try:
        backend_url = os.environ.get("BACKEND_URL", "http://localhost:7790")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{backend_url}/mcp/registry/tools/dry-run",
                json={"tool_name": tool, "arguments": arguments},
                timeout=30.0,
            )
            return response.text
    except Exception as e:
        return f"MCP tool call failed: {str(e)}"


@mcp.tool()
async def create_connector(name: str, connector_type: str, config: dict) -> str:
    """Create a new data connector.

    Args:
        name: Name for the new connector
        connector_type: Type of connector (postgres, azure_blob, filesystem)
        config: Configuration for the connector
    """
    return f"Connector '{name}' ({connector_type}) creation request received. Use the backend API to complete setup."


@mcp.tool()
async def create_tool(name: str, description: str, code: str) -> str:
    """Create a new custom tool.

    Args:
        name: Name for the new tool
        description: Description of what the tool does
        code: Python code for the tool
    """
    return f"Tool '{name}' creation request received. Use the backend API to register and test."


# ─── Prompts ──────────────────────────────────────────────────────────────────

@mcp.prompt()
def tool_selector(intent: str, tools: str) -> str:
    """Select the best tool(s) for a given intent."""
    return f"Given intent '{intent}' and available tools: {tools}, select the best tool(s)."


@mcp.prompt()
def query_planner(question: str, resources: str) -> str:
    """Plan a multi-step query execution."""
    return f"Plan execution for: '{question}' using resources: {resources}"


if __name__ == "__main__":
    from backend.config import settings
    port = settings.mcp_server_port
    logger.info(f"Starting MCP server on port {port}")
    mcp.run(transport="sse", host="0.0.0.0", port=port)
