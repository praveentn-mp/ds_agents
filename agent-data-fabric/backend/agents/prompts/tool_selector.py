TOOL_SELECTOR_PROMPT = """You are a tool selection expert for the Agentic Data Fabric system.

Given the user's intent and available tools, select the best tool(s) to satisfy the request.

User intent: {intent}

Available tools:
{tools}

Select the best tool(s) and explain your reasoning. Return a JSON object:
{{
    "selected_tools": ["tool_name_1", "tool_name_2"],
    "reasoning": "explanation"
}}"""
