"""Meta agent node — handles system/platform queries (list tools, connectors, ingestion status)."""

import json
from backend.agents.state import ADFAgentState
from backend.agents.llm import invoke_llm
from backend.database import async_session
from backend.models.custom_tool import CustomTool
from backend.models.connector import Connector
from sqlalchemy import select, text


async def meta_agent(state: ADFAgentState) -> dict:
    """Answer questions about the system — tools, connectors, ingested data, etc."""
    user_message = state["messages"][-1]["content"]
    all_usages = []

    info_sections = []

    try:
        async with async_session() as db:
            # Gather system info
            # 1. Custom tools
            tools_result = await db.execute(
                select(CustomTool).where(CustomTool.is_active == True)
            )
            tools = list(tools_result.scalars().all())
            if tools:
                tools_md = "| Name | Description | Version |\n| --- | --- | --- |\n"
                for t in tools:
                    tools_md += f"| {t.name} | {t.description or 'No description'} | v{t.current_version} |\n"
                info_sections.append(("Custom Tools", tools_md, len(tools)))
            else:
                info_sections.append(("Custom Tools", "No custom tools created yet.", 0))

            # 2. Connectors
            conn_result = await db.execute(
                select(Connector).where(Connector.is_active == True)
            )
            connectors = list(conn_result.scalars().all())
            if connectors:
                conn_md = "| Name | Type | Description |\n| --- | --- | --- |\n"
                for c in connectors:
                    conn_md += f"| {c.name} | {c.connector_type} | {c.description or '-'} |\n"
                info_sections.append(("Connectors", conn_md, len(connectors)))

            # 3. Ingested data
            ingestion_result = await db.execute(text(
                "SELECT table_name, table_description, row_count, column_count "
                "FROM ingestion_metadata ORDER BY created_at DESC LIMIT 20"
            ))
            ingested = ingestion_result.fetchall()
            if ingested:
                ing_md = "| Table | Description | Rows | Columns |\n| --- | --- | --- | --- |\n"
                for row in ingested:
                    ing_md += f"| {row[0]} | {row[1] or '-'} | {row[2]:,} | {row[3]} |\n"
                info_sections.append(("Ingested Data", ing_md, len(ingested)))

            # 4. Vector index stats
            vec_stats = []
            for tbl in ["vec_table_index", "vec_column_index", "vec_value_index", "vec_chunk_index"]:
                count_result = await db.execute(text(f'SELECT COUNT(*) FROM "{tbl}"'))
                count = count_result.scalar() or 0
                vec_stats.append(f"- **{tbl}**: {count:,} entries")
            info_sections.append(("Vector Index Stats", "\n".join(vec_stats), None))

    except Exception as e:
        info_sections.append(("Error", f"Failed to gather system info: {str(e)}", None))

    # Build context for LLM
    context = ""
    for title, content, count in info_sections:
        context += f"\n### {title}"
        if count is not None:
            context += f" ({count})"
        context += f"\n{content}\n"

    # Ask LLM to answer user's specific question using the gathered info
    prompt = f"""The user is asking about the system/platform. Answer their question using the information below.

USER QUESTION: "{user_message}"

SYSTEM INFORMATION:
{context}

Provide a clear, well-formatted answer. Use markdown tables if appropriate.
Include only the information relevant to the user's question.
If they ask about tools, show the tools table. If they ask about connectors, show connectors. Etc."""

    try:
        response, usage = await invoke_llm(prompt)
        all_usages.append(usage)
    except Exception:
        response = context  # fallback: just show raw info

    # Build result
    result = {
        "final_response": response,
        "current_step": 3,
        "trace_events": [{
            "type": "meta_query",
            "agent": "meta_agent",
            "status": "success",
            "payload": {
                "tools_count": len(tools) if 'tools' in dir() else 0,
                "connectors_count": len(connectors) if 'connectors' in dir() else 0,
            },
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
            "latency_ms": u.latency_ms, "node": "meta_agent",
        })
    result["token_count"] = {"input": total_input, "output": total_output, "cache": total_cache}
    result["llm_calls"] = llm_calls
    return result
