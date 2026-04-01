CONNECTOR_VS_TOOL_DECIDER_PROMPT = """Given the user's request, decide whether to use a data connector, an MCP tool, or a hybrid approach.

Request: {request}

Available connectors:
{connectors}

Available MCP tools:
{tools}

Decide the best path. Return a JSON object:
{{
    "path": "connector|tool|hybrid",
    "reasoning": "explanation",
    "steps": ["step1", "step2"]
}}"""
