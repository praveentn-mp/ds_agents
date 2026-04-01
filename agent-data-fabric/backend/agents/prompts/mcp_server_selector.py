MCP_SERVER_SELECTOR_PROMPT = """Given the task, select the best Docker MCP server to handle it.

Task: {task}

Available MCP servers:
{servers}

Return a JSON object:
{{
    "server": "server_name",
    "tool": "tool_name",
    "reasoning": "explanation"
}}"""
