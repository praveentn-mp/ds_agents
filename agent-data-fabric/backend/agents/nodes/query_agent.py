"""Query agent node — discover schema, generate SQL, execute, return results."""

import json
import re
from backend.agents.state import ADFAgentState
from backend.agents.llm import invoke_llm
from backend.database import async_session
from backend.models.connector import Connector
from backend.services.connector_service import _build_connector
from sqlalchemy import select


async def _get_postgres_connector() -> tuple:
    """Find first active postgres connector and return (record, instance)."""
    async with async_session() as db:
        result = await db.execute(
            select(Connector).where(
                Connector.connector_type == "postgres",
                Connector.is_active == True,
            ).order_by(Connector.created_at)
        )
        connector = result.scalar_one_or_none()
        if not connector:
            return None, None
        instance = _build_connector(connector)
        return connector, instance


def _extract_sql(text: str) -> str | None:
    """Extract SQL from LLM response (may be in a code block or plain)."""
    # Try ```sql ... ``` block first
    match = re.search(r"```(?:sql)?\s*\n?(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    # Try to find a SELECT/WITH statement
    match = re.search(r"((?:SELECT|WITH)\b.+?)(?:\n\n|\Z)", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip().rstrip(";") + ";"
    return None


def _format_results(columns: list[str], rows: list[dict], total: int) -> str:
    """Format query results into a readable markdown table."""
    if not rows:
        return "The query returned no results."

    # Build markdown table
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    lines = [header, separator]
    for row in rows[:50]:  # Cap display at 50 rows
        vals = []
        for col in columns:
            v = row.get(col, "")
            if v is None:
                vals.append("NULL")
            elif isinstance(v, float):
                vals.append(f"{v:,.2f}")
            else:
                vals.append(str(v))
        lines.append("| " + " | ".join(vals) + " |")
    table = "\n".join(lines)
    if total > 50:
        table += f"\n\n*Showing 50 of {total} rows.*"
    return table


async def query_agent(state: ADFAgentState) -> dict:
    """Discover schema, generate SQL, execute against the DB, return formatted results."""
    user_message = state["messages"][-1]["content"]

    # ── Step 1: Get the postgres connector ──
    connector_record, connector_instance = await _get_postgres_connector()
    if not connector_instance:
        return {
            "final_response": "No active PostgreSQL connector is configured. Please add one in the Connectors page.",
            "current_step": 3,
            "trace_events": [{"type": "query", "agent": "query_agent", "status": "error",
                              "payload": {"error": "no_connector"}, "sequence": 3}],
        }

    try:
        # ── Step 2: Discover schema ──
        schema = await connector_instance.discover_schema()
        b2b_tables = [t for t in schema.get("tables", []) if t["name"].startswith("b2b_")]
        if not b2b_tables:
            # Fall back to all public tables
            b2b_tables = [t for t in schema.get("tables", []) if t.get("schema") == "public"]

        schema_desc = ""
        for table in b2b_tables:
            cols = ", ".join([f"{c['name']} ({c['type']})" for c in table["columns"]])
            schema_desc += f"- {table['name']}: {cols}\n"

        # ── Step 3: Ask LLM to generate SQL ──
        prompt = f"""You are a SQL expert. Given the database schema and user question, generate a PostgreSQL query.

DATABASE SCHEMA:
{schema_desc}

USER QUESTION: "{user_message}"

RULES:
- Return ONLY the SQL query inside a ```sql code block
- Use only tables and columns from the schema above
- For revenue/money questions, use the b2b_companies.annual_revenue or b2b_deals.amount columns
- JOIN tables using UUID foreign keys (company_id, deal_id, etc.)
- Add ORDER BY and LIMIT for readability
- Do NOT use INSERT, UPDATE, DELETE, DROP, or any write operations
- After the SQL block, add a one-sentence plain-English explanation of what the query does"""

        sql_response, usage = await invoke_llm(prompt)
        generated_sql = _extract_sql(sql_response)

        if not generated_sql:
            await connector_instance.close()
            return _make_result(
                f"I understood your question but couldn't generate a valid SQL query. Here's what I was thinking:\n\n{sql_response}",
                state, usage, user_message, sql=None
            )

        # Safety: reject write operations
        sql_upper = generated_sql.strip().upper()
        if any(sql_upper.startswith(kw) for kw in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE"]):
            await connector_instance.close()
            return _make_result(
                "I can only run read-only queries. Please rephrase your question as a data retrieval request.",
                state, usage, user_message, sql=generated_sql
            )

        # ── Step 4: Execute the SQL ──
        rows = await connector_instance.execute_query(generated_sql)
        await connector_instance.close()

        if not rows:
            explanation = sql_response.split("```")[-1].strip() if "```" in sql_response else ""
            return _make_result(
                f"The query returned no results.\n\n**SQL executed:**\n```sql\n{generated_sql}\n```\n{explanation}",
                state, usage, user_message, sql=generated_sql
            )

        columns = list(rows[0].keys())
        total = len(rows)
        table_md = _format_results(columns, rows, total)

        # Build explanation from LLM response
        explanation = ""
        parts = sql_response.split("```")
        if len(parts) >= 3:
            explanation = parts[-1].strip()

        response = f"{table_md}\n\n**SQL:**\n```sql\n{generated_sql}\n```"
        if explanation:
            response += f"\n\n{explanation}"

        return _make_result(response, state, usage, user_message, sql=generated_sql, row_count=total)

    except Exception as e:
        try:
            await connector_instance.close()
        except Exception:
            pass
        error_msg = str(e)
        return {
            "final_response": f"I tried to query the database but encountered an error:\n\n`{error_msg}`\n\nPlease check that the connector is properly configured.",
            "current_step": 3,
            "trace_events": [{"type": "query", "agent": "query_agent", "status": "error",
                              "payload": {"error": error_msg}, "sequence": 3}],
        }


def _make_result(response: str, state: ADFAgentState, usage, user_message: str,
                 sql: str | None = None, row_count: int = 0) -> dict:
    """Build the return dict with response, trace events, and token tracking."""
    result = {
        "final_response": response,
        "current_step": 3,
        "trace_events": [{
            "type": "query",
            "agent": "query_agent",
            "tool": "QueryResource",
            "status": "success",
            "payload": {"query": user_message, "sql": sql, "row_count": row_count},
            "sequence": 3,
        }],
    }

    if usage:
        token_count = state.get("token_count", {"input": 0, "output": 0, "cache": 0})
        result["token_count"] = {
            "input": token_count["input"] + usage.tokens_input,
            "output": token_count["output"] + usage.tokens_output,
            "cache": token_count["cache"] + usage.tokens_cache,
        }
        result["llm_calls"] = [{"model": usage.model, "tokens_input": usage.tokens_input,
                                 "tokens_output": usage.tokens_output, "tokens_cache": usage.tokens_cache,
                                 "latency_ms": usage.latency_ms, "node": "query_agent"}]

    return result
