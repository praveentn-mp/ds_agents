"""Tool agent node — finds matching tools and executes them."""

import json
from backend.agents.state import ADFAgentState
from backend.agents.llm import invoke_llm
from backend.database import async_session
from backend.models.custom_tool import CustomTool
from backend.services.tool_service import execute_tool
from sqlalchemy import select


async def tool_agent(state: ADFAgentState) -> dict:
    """Find matching tools, let LLM decide which to use, then execute."""
    user_message = state["messages"][-1]["content"]
    all_usages = []

    # Step 1: Load available custom tools from DB
    tools_list = []
    try:
        async with async_session() as db:
            result = await db.execute(
                select(CustomTool).where(CustomTool.is_active == True)
            )
            tools_list = list(result.scalars().all())
    except Exception:
        pass

    if not tools_list:
        return {
            "final_response": "No custom tools are available. You can create tools in the Tools page — describe what you need and AI will generate one for you.",
            "current_step": 3,
            "trace_events": [{"type": "tool_call", "agent": "tool_agent", "status": "no_tools",
                              "payload": {"request": user_message}, "sequence": 3}],
        }

    # Step 2: LLM selects the best tool and arguments
    tool_descriptions = "\n".join([
        f"- {t.name} (id: {t.id}): {t.description or 'No description'}\n  Input schema: {json.dumps(t.input_schema or {})}\n  Code: {t.code[:200]}..."
        for t in tools_list
    ])

    prompt = f"""You are a tool execution assistant. Given the user's request and available tools, decide which tool to use and what arguments to pass.

Available tools:
{tool_descriptions}

User request: "{user_message}"

If a suitable tool exists, respond with JSON:
{{"tool_name": "<name>", "tool_id": "<id>", "arguments": {{}}, "explanation": "why this tool"}}

If no tool matches the request, respond with:
{{"tool_name": null, "explanation": "why no tool matches"}}

Return ONLY the JSON, no markdown."""

    try:
        content, usage = await invoke_llm(prompt)
        all_usages.append(usage)
        content = content.strip()
        if "```" in content:
            parts = content.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    content = part
                    break
        decision = json.loads(content)
    except Exception as e:
        decision = {"tool_name": None, "explanation": f"Failed to parse tool selection: {e}"}

    tool_name = decision.get("tool_name")
    tool_id = decision.get("tool_id")
    arguments = decision.get("arguments", {})
    explanation = decision.get("explanation", "")

    # Step 3: If no tool selected, respond with explanation
    if not tool_name:
        return _build_result(
            f"I looked at the available tools but none match your request.\n\n{explanation}\n\nYou can create a new tool in the Tools page.",
            state, all_usages,
            trace_status="no_match",
            trace_payload={"request": user_message, "explanation": explanation},
        )

    # Step 4: Execute the selected tool
    try:
        async with async_session() as db:
            exec_result = await execute_tool(db, tool_id, arguments)
    except Exception as e:
        exec_result = {"success": False, "error": str(e), "duration_ms": 0}

    if exec_result.get("success"):
        result_data = exec_result.get("result")

        # Build a rich formatted response for tool results with SQL + table
        response_parts = []

        if isinstance(result_data, dict):
            sql_used = result_data.get("sql", "")
            data_rows = result_data.get("data", [])
            columns = result_data.get("columns", [])
            row_count = result_data.get("row_count", len(data_rows))

            # If we have structured data, build markdown table
            if data_rows and columns:
                response_parts.append(f"**Tool: {tool_name}**\n")
                # Build markdown table
                header = "| " + " | ".join(str(c) for c in columns) + " |"
                separator = "| " + " | ".join("---" for _ in columns) + " |"
                rows_md = []
                for row in data_rows[:50]:  # cap at 50
                    if isinstance(row, dict):
                        cells = [str(row.get(c, "")) for c in columns]
                    else:
                        cells = [str(v) for v in row]
                    rows_md.append("| " + " | ".join(cells) + " |")
                table_md = "\n".join([header, separator] + rows_md)
                response_parts.append(table_md)
                if row_count > 50:
                    response_parts.append(f"\n*Showing 50 of {row_count} rows*")
            elif row_count == 0:
                response_parts.append(f"**Tool: {tool_name}** returned no results.")

            if sql_used:
                response_parts.append(f"\n**SQL:**\n```sql\n{sql_used}\n```")

            if not data_rows and not sql_used:
                # Generic result
                result_str = json.dumps(result_data, indent=2)
                response_parts.append(f"**Tool: {tool_name}**\n\n```json\n{result_str}\n```")
        else:
            result_str = json.dumps(result_data, indent=2) if isinstance(result_data, (dict, list)) else str(result_data)
            response_parts.append(f"**Tool: {tool_name}**\n\n```\n{result_str}\n```")

        response = "\n".join(response_parts) if response_parts else f"**Tool: {tool_name}** executed successfully."

        # Only ask LLM to add natural language summary if we have data
        if isinstance(result_data, dict) and result_data.get("data"):
            try:
                summary_prompt = f"""The user asked: "{user_message}"
The tool "{tool_name}" returned {result_data.get('row_count', 0)} rows.
Add a ONE SENTENCE summary of the results. Just the summary text, no tables or SQL."""
                summary, fmt_usage = await invoke_llm(summary_prompt)
                all_usages.append(fmt_usage)
                response = summary.strip() + "\n\n" + response
            except Exception:
                pass

        return _build_result(
            response,
            state, all_usages,
            trace_status="success",
            trace_payload={"tool": tool_name, "arguments": arguments, "duration_ms": exec_result.get("duration_ms", 0)},
        )
    else:
        error = exec_result.get("error", "Unknown error")
        return _build_result(
            f"I tried to run **{tool_name}** but it failed:\n\n`{error}`\n\n{explanation}",
            state, all_usages,
            trace_status="error",
            trace_payload={"tool": tool_name, "error": error},
        )


def _build_result(response: str, state: ADFAgentState, all_usages: list,
                  trace_status: str, trace_payload: dict) -> dict:
    """Build the standard result dict with trace events and token tracking."""
    result = {
        "final_response": response,
        "current_step": 3,
        "trace_events": [{
            "type": "tool_call",
            "agent": "tool_agent",
            "status": trace_status,
            "payload": trace_payload,
            "sequence": 3,
        }],
    }

    token_count = state.get("token_count", {"input": 0, "output": 0, "cache": 0})
    total_input = token_count["input"]
    total_output = token_count["output"]
    total_cache = token_count["cache"]
    llm_calls = []
    for u in all_usages:
        total_input += u.tokens_input
        total_output += u.tokens_output
        total_cache += u.tokens_cache
        llm_calls.append({
            "model": u.model, "tokens_input": u.tokens_input,
            "tokens_output": u.tokens_output, "tokens_cache": u.tokens_cache,
            "latency_ms": u.latency_ms, "node": "tool_agent",
        })
    result["token_count"] = {"input": total_input, "output": total_output, "cache": total_cache}
    result["llm_calls"] = llm_calls
    return result
