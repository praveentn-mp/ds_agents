"""Query agent v3 — entity extraction → per-entity hybrid search → rerank → resolve → SQL/RAG → response.

Flow (per user specification):
  1. User enters query
  2. Find intent — if generic/invalid respond accordingly; if about data proceed
  3. LLM extracts entities (keys and values)
  4. Create embedding of each entity
  5. Run hybrid search for each entity against ALL vector indices (table, column, value, chunks)
  6. Consolidate results for all entities (table, column, value, chunks)
  7. Rerank by score + table-column-value-chunk mapping
  8. Take top N (configurable) reranked matched entities
  9. Use with user query + LLM + table metadata to resolve: structured T2SQL or unstructured chunks
  10. Execute SQL for structured; hybrid search on chunks for unstructured
  11. RAG with output (SQL results or top-N chunks)
  12. Show final response with table, SQL executed, chunk details
"""

import json
import re
from decimal import Decimal
from datetime import date, datetime

from backend.agents.state import ADFAgentState
from backend.agents.llm import invoke_llm
from backend.database import async_session
from backend.models.connector import Connector
from backend.services.connector_service import _build_connector
from backend.services.search_service import hybrid_search, get_table_schema_from_metadata, SearchResponse
from sqlalchemy import select

# ── Config ───────────────────────────────────────────────────────────────────
TOP_N_RERANKED = 5          # max reranked entities to use for resolution
MIN_SEARCH_SCORE = 0.15     # lower threshold to catch more candidates
SEARCH_TOP_K = 15           # per-index results per search query


# ── Helpers ──────────────────────────────────────────────────────────────────

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
    match = re.search(r"```(?:sql)?\s*\n?(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r"((?:SELECT|WITH)\b.+?)(?:\n\n|\Z)", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip().rstrip(";") + ";"
    return None


def _make_serializable(obj):
    """Convert Decimal/date/etc to JSON-safe types."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(i) for i in obj]
    return obj


def _format_results(columns: list[str], rows: list[dict], total: int) -> str:
    """Format query results into a readable markdown table."""
    if not rows:
        return "The query returned no results."
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    lines = [header, separator]
    for row in rows[:50]:
        vals = []
        for col in columns:
            v = row.get(col, "")
            if v is None:
                vals.append("NULL")
            elif isinstance(v, float):
                vals.append(f"{v:,.2f}")
            elif isinstance(v, Decimal):
                vals.append(f"{float(v):,.2f}")
            else:
                vals.append(str(v))
        lines.append("| " + " | ".join(vals) + " |")
    table = "\n".join(lines)
    if total > 50:
        table += f"\n\n*Showing 50 of {total} rows.*"
    return table


def _format_search_context(table_matches, column_matches, value_matches, chunk_matches) -> str:
    """Format search results into context for the LLM."""
    lines = []
    if table_matches:
        lines.append("**Matched Tables:**")
        for r in table_matches[:5]:
            lines.append(f"  - {r.table_name} (score: {r.score:.3f}): {r.description or 'no description'}")
    if column_matches:
        lines.append("**Matched Columns:**")
        for r in column_matches[:10]:
            lines.append(f"  - {r.table_name}.{r.column_name} (score: {r.score:.3f}): {r.description or r.data_type or ''}")
    if value_matches:
        lines.append("**Matched Values:**")
        for r in value_matches[:10]:
            lines.append(f"  - {r.table_name}.{r.column_name} = \"{r.value_text}\" (score: {r.score:.3f})")
    if chunk_matches:
        lines.append("**Matched Document Chunks:**")
        for r in chunk_matches[:5]:
            snippet = r.chunk_text[:200] + "..." if len(r.chunk_text) > 200 else r.chunk_text
            lines.append(f"  - [{r.source_file}] (score: {r.score:.3f}): {snippet}")
    return "\n".join(lines) if lines else "No matches found in vector indices."


# ── Step 3: Entity Extraction ────────────────────────────────────────────────

async def _extract_entities(user_message: str, all_usages: list) -> list[str]:
    """Use LLM to extract key entities/values from the user query for targeted search."""
    prompt = f"""Extract the key entities, nouns, and specific values from this user question that should be searched in a database.

USER QUESTION: "{user_message}"

Return a JSON array of strings — each string is one entity or value to search for.
Include: table/dataset names, column names, specific filter values, business terms, company names, product names.
Exclude: generic words like "show", "get", "list", "details", "data", "me", "the", "of".

Examples:
- "show me wine data" → ["wine"]
- "top customers by revenue in New York" → ["customers", "revenue", "New York"]
- "details of Globex Industries" → ["Globex Industries"]
- "sales by region for Q4 2024" → ["sales", "region", "Q4 2024"]
- "get me the details of globex company" → ["globex", "company"]

Return ONLY the JSON array, nothing else."""

    response, usage = await invoke_llm(prompt)
    all_usages.append(usage)

    try:
        content = response.strip()
        if "```" in content:
            parts = content.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("["):
                    content = part
                    break
        entities = json.loads(content)
        if isinstance(entities, list):
            return [str(e).strip() for e in entities if e]
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: simple word extraction
    stop_words = {"show", "get", "list", "give", "tell", "what", "which", "the", "for",
                  "from", "with", "about", "details", "data", "all", "and", "are", "how",
                  "many", "me", "of", "please", "can", "you", "i", "want", "need", "find"}
    words = [w for w in user_message.split() if len(w) > 2 and w.lower() not in stop_words]
    return words


# ── Steps 4-7: Per-entity hybrid search + consolidate + rerank ───────────────

async def _search_and_consolidate(entities: list[str], user_message: str) -> dict:
    """Run hybrid search for each entity + full query, consolidate and rerank results."""
    all_search_queries = entities + [user_message]
    merged_table = []
    merged_column = []
    merged_value = []
    merged_chunk = []
    seen_tables = set()
    seen_columns = set()
    seen_values = set()

    async with async_session() as search_db:
        for search_query in all_search_queries:
            sr = await hybrid_search(
                query=search_query,
                db=search_db,
                top_k=SEARCH_TOP_K,
                min_score=MIN_SEARCH_SCORE,
            )
            for r in sr.table_matches:
                key = r.table_name
                if key not in seen_tables:
                    seen_tables.add(key)
                    merged_table.append(r)
                else:
                    for existing in merged_table:
                        if existing.table_name == key and r.score > existing.score:
                            existing.score = r.score
                            break
            for r in sr.column_matches:
                key = (r.table_name, r.column_name)
                if key not in seen_columns:
                    seen_columns.add(key)
                    merged_column.append(r)
                else:
                    for existing in merged_column:
                        if (existing.table_name, existing.column_name) == key and r.score > existing.score:
                            existing.score = r.score
                            break
            for r in sr.value_matches:
                key = (r.table_name, r.column_name, r.value_text)
                if key not in seen_values:
                    seen_values.add(key)
                    merged_value.append(r)
                else:
                    for existing in merged_value:
                        if (existing.table_name, existing.column_name, existing.value_text) == key and r.score > existing.score:
                            existing.score = r.score
                            break
            for r in sr.chunk_matches:
                merged_chunk.append(r)

    # Sort all by score descending (rerank)
    merged_table.sort(key=lambda r: r.score, reverse=True)
    merged_column.sort(key=lambda r: r.score, reverse=True)
    merged_value.sort(key=lambda r: r.score, reverse=True)
    merged_chunk.sort(key=lambda r: r.score, reverse=True)

    # Deduplicate chunks by text
    seen_texts = set()
    deduped_chunks = []
    for r in merged_chunk:
        if r.chunk_text not in seen_texts:
            seen_texts.add(r.chunk_text)
            deduped_chunks.append(r)
    merged_chunk = deduped_chunks

    # Take top N reranked matches
    top_table = merged_table[:TOP_N_RERANKED]
    top_column = merged_column[:TOP_N_RERANKED * 3]
    top_value = merged_value[:TOP_N_RERANKED * 2]
    top_chunk = merged_chunk[:TOP_N_RERANKED]

    # Resolve entities for SQL generation
    resolved_tables = list(dict.fromkeys(
        r.table_name for r in (top_table + top_column + top_value) if r.table_name
    ))
    resolved_columns: dict[str, list[str]] = {}
    for r in top_column:
        if r.table_name and r.column_name:
            resolved_columns.setdefault(r.table_name, [])
            if r.column_name not in resolved_columns[r.table_name]:
                resolved_columns[r.table_name].append(r.column_name)
    resolved_values: dict[str, list[str]] = {}
    for r in top_value:
        if r.table_name and r.column_name and r.value_text:
            key = f"{r.table_name}.{r.column_name}"
            resolved_values.setdefault(key, [])
            if r.value_text not in resolved_values[key]:
                resolved_values[key].append(r.value_text)

    return {
        "table_matches": top_table,
        "column_matches": top_column,
        "value_matches": top_value,
        "chunk_matches": top_chunk,
        "resolved_tables": resolved_tables,
        "resolved_columns": resolved_columns,
        "resolved_values": resolved_values,
        "has_structured": bool(top_table or top_column or top_value),
        "has_chunks": bool(top_chunk),
    }


# ── Step 9: Resolve data type (structured SQL vs unstructured chunks) ────────

async def _resolve_data_type(user_message: str, search_results: dict, all_usages: list) -> str:
    """Determine whether to use structured SQL or unstructured chunk search."""
    has_structured = search_results["has_structured"]
    has_chunks = search_results["has_chunks"]

    if has_structured and not has_chunks:
        return "structured"
    if has_chunks and not has_structured:
        return "unstructured"
    if not has_structured and not has_chunks:
        return "fallback"

    # Both — let LLM decide
    prompt = f"""Given the user question and search results, decide the best approach.

User question: "{user_message}"

Structured data matches (database tables/columns):
  Tables: {[r.table_name for r in search_results['table_matches']]}
  Values: {[(r.table_name, r.column_name, r.value_text) for r in search_results['value_matches'][:5]]}

Unstructured data matches (document chunks):
  Chunks: {len(search_results['chunk_matches'])} matches

Respond with ONLY "structured" or "unstructured"."""

    response, usage = await invoke_llm(prompt)
    all_usages.append(usage)
    if "unstructured" in response.strip().lower():
        return "unstructured"
    return "structured"


# ── Step 10a: Structured SQL path ────────────────────────────────────────────

async def _sql_path(user_message: str, connector_instance, search_results: dict, all_usages: list) -> dict:
    """Generate SQL from search context, execute, feedback loop if empty."""

    async with async_session() as db:
        schema_desc = await get_table_schema_from_metadata(db, search_results["resolved_tables"])

    if not schema_desc:
        schema = await connector_instance.discover_schema()
        all_tables = schema.get("tables", [])
        target_tables = [t for t in all_tables if t["name"] in search_results["resolved_tables"]]
        if not target_tables:
            target_tables = [t for t in all_tables if t["name"].startswith("ingested_") or t["name"].startswith("b2b_")]
        schema_desc = ""
        for table in target_tables:
            cols = ", ".join([f'"{c["name"]}" ({c["type"]})' for c in table["columns"]])
            schema_desc += f"- {table['name']}: {cols}\n"

    value_hints = ""
    if search_results["resolved_values"]:
        value_hints = "\nKNOWN VALUES (use these exact values in WHERE clauses):\n"
        for key, vals in search_results["resolved_values"].items():
            value_hints += f"  - {key}: {', '.join(repr(v) for v in vals[:10])}\n"

    search_context = _format_search_context(
        search_results["table_matches"],
        search_results["column_matches"],
        search_results["value_matches"],
        search_results["chunk_matches"],
    )

    prompt = f"""You are a SQL expert. Generate a PostgreSQL query to answer the user's question.

SEARCH CONTEXT (vector search matches for the user's question):
{search_context}

DATABASE SCHEMA (these are the exact table and column names — use them EXACTLY as shown):
{schema_desc}
{value_hints}

USER QUESTION: "{user_message}"

CRITICAL RULES:
- Return ONLY the SQL query inside a ```sql code block
- Use EXACT table and column names from the schema above
- Column names are CASE-SENSITIVE — you MUST double-quote them: SELECT "Wine", "Country" FROM ingested_wine
- Always double-quote column names in SELECT, WHERE, ORDER BY, GROUP BY, and JOIN clauses
- Table names do NOT need quoting (they are lowercase)
- Use exact values from KNOWN VALUES when filtering
- JOIN tables using foreign key relationships where appropriate
- Add ORDER BY and LIMIT for readability
- Do NOT use INSERT, UPDATE, DELETE, DROP, or any write operations
- After the SQL block, add a one-sentence plain-English explanation"""

    sql_response, usage = await invoke_llm(prompt)
    all_usages.append(usage)
    generated_sql = _extract_sql(sql_response)

    if not generated_sql:
        return {
            "answer": f"I understood your question but couldn't generate a valid SQL query.\n\n{sql_response}",
            "trace": {"type": "query_execution", "agent": "query_agent", "status": "no_sql",
                      "payload": {"query": user_message}, "sequence": 4},
        }

    sql_upper = generated_sql.strip().upper()
    if any(sql_upper.startswith(kw) for kw in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE"]):
        return {
            "answer": "I can only run read-only queries. Please rephrase your question.",
            "trace": {"type": "query_execution", "agent": "query_agent", "status": "blocked",
                      "payload": {"sql": generated_sql}, "sequence": 4},
        }

    try:
        rows = await connector_instance.execute_query(generated_sql)
        rows = _make_serializable(rows)
    except Exception as e:
        return {
            "answer": f"SQL execution error: `{str(e)}`\n\n**SQL attempted:**\n```sql\n{generated_sql}\n```",
            "trace": {"type": "query_execution", "agent": "query_agent", "status": "sql_error",
                      "payload": {"sql": generated_sql, "error": str(e)}, "sequence": 4},
        }

    if not rows:
        retry = await _sql_retry(user_message, connector_instance, generated_sql, schema_desc, all_usages)
        if retry:
            return retry
        explanation = sql_response.split("```")[-1].strip() if "```" in sql_response else ""
        return {
            "answer": f"The query returned no results.\n\n**SQL executed:**\n```sql\n{generated_sql}\n```\n{explanation}",
            "trace": {"type": "query_execution", "agent": "query_agent", "status": "empty",
                      "payload": {"sql": generated_sql}, "sequence": 4},
        }

    columns = list(rows[0].keys())
    total = len(rows)
    table_md = _format_results(columns, rows, total)

    explanation = ""
    parts = sql_response.split("```")
    if len(parts) >= 3:
        explanation = parts[-1].strip()

    tables_used = ", ".join(search_results["resolved_tables"][:3]) if search_results["resolved_tables"] else "unknown"
    response = f"**Source table(s):** {tables_used}\n\n{table_md}\n\n**SQL:**\n```sql\n{generated_sql}\n```"
    if explanation:
        response += f"\n\n{explanation}"

    return {
        "answer": response,
        "trace": {"type": "query_execution", "agent": "query_agent", "tool": "QueryResource",
                  "status": "success", "payload": {"sql": generated_sql, "row_count": total,
                                                    "tables": search_results["resolved_tables"]}, "sequence": 4},
    }


async def _sql_retry(user_message, connector_instance, failed_sql, schema_desc, all_usages) -> dict | None:
    """Feedback loop: if first SQL returned empty, try a broader approach."""
    prompt = f"""The following SQL query returned NO results:
```sql
{failed_sql}
```

The user asked: "{user_message}"

Available schema (column names are CASE-SENSITIVE, always double-quote them):
{schema_desc}

Generate a BROADER SQL query. Strategies:
- Remove overly specific WHERE clauses
- Use ILIKE instead of exact matches for text
- Try different JOINs or remove JOINs
- Select from a broader table
- Remember to double-quote all column names

Return ONLY the SQL inside a ```sql block. Return "NO_DATA" if data simply doesn't exist."""

    retry_response, usage = await invoke_llm(prompt)
    all_usages.append(usage)

    if "NO_DATA" in retry_response:
        return None

    retry_sql = _extract_sql(retry_response)
    if not retry_sql:
        return None

    sql_upper = retry_sql.strip().upper()
    if any(sql_upper.startswith(kw) for kw in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE"]):
        return None

    try:
        rows = await connector_instance.execute_query(retry_sql)
        rows = _make_serializable(rows)
    except Exception:
        return None
    if not rows:
        return None

    columns = list(rows[0].keys())
    total = len(rows)
    table_md = _format_results(columns, rows, total)

    return {
        "answer": f"{table_md}\n\n**SQL (refined):**\n```sql\n{retry_sql}\n```\n\n*Initial query returned no results — this is a broader search.*",
        "trace": {"type": "query_execution", "agent": "query_agent", "tool": "QueryResource",
                  "status": "success_retry", "payload": {"sql": retry_sql, "row_count": total}, "sequence": 4},
    }


# ── Step 10b: Unstructured RAG path ─────────────────────────────────────────

async def _rag_path(user_message: str, search_results: dict, all_usages: list) -> dict:
    """Answer from document chunks found via vector search."""
    chunks = search_results["chunk_matches"]
    if not chunks:
        return {
            "answer": "No relevant document chunks were found for your query.",
            "trace": {"type": "rag_execution", "agent": "query_agent", "status": "no_chunks",
                      "payload": {"query": user_message}, "sequence": 4},
        }

    chunks_context = ""
    for r in chunks[:5]:
        chunks_context += f"[{r.source_file}, score={r.score:.3f}]:\n{r.chunk_text}\n\n"

    prompt = f"""Answer the user's question using the following document excerpts.

DOCUMENT EXCERPTS:
{chunks_context}

USER QUESTION: "{user_message}"

RULES:
- Base your answer ONLY on the provided excerpts
- If the excerpts don't contain enough information, say so
- Cite the source file when referencing specific information
- Be concise and direct"""

    response, usage = await invoke_llm(prompt)
    all_usages.append(usage)

    chunk_details = "\n\n**Sources:**\n"
    for r in chunks[:5]:
        chunk_details += f"- {r.source_file} (relevance: {r.score:.2f})\n"

    return {
        "answer": response + chunk_details,
        "trace": {"type": "rag_execution", "agent": "query_agent", "status": "success",
                  "payload": {"chunks_used": len(chunks), "query": user_message}, "sequence": 4},
    }


# ── Fallback: schema discovery when no vector results found ──────────────────

async def _fallback_path(user_message: str, connector_instance, all_usages: list) -> dict:
    """Fallback: full schema discovery when vector search returns nothing."""
    schema = await connector_instance.discover_schema()
    all_tables = [t for t in schema.get("tables", []) if t.get("schema") not in ("pg_catalog", "information_schema")]

    _INTERNAL = {"vec_table_index", "vec_column_index", "vec_value_index", "vec_chunk_index",
                 "ingestion_metadata", "column_metadata", "connectors", "connector_schemas",
                 "connector_perms", "tool_perms", "roles",
                 "mcp_resources", "mcp_tools", "mcp_servers", "mcp_prompts",
                 "sync_jobs", "sql_query_history", "llm_calls", "users",
                 "conversations", "messages", "rag_documents", "rag_chunks",
                 "custom_tools", "tool_versions", "execution_traces", "refresh_tokens",
                 "alembic_version"}

    user_tables = [t for t in all_tables if t["name"] not in _INTERNAL and t.get("schema") == "public"]
    if not user_tables:
        user_tables = [t for t in all_tables if t["name"] not in _INTERNAL]

    schema_desc = ""
    for table in user_tables:
        cols = ", ".join([f'"{c["name"]}" ({c["type"]})' for c in table["columns"]])
        schema_desc += f"- {table['name']}: {cols}\n"

    prompt = f"""You are a SQL expert. Given the database schema and user question, generate a PostgreSQL query.

DATABASE SCHEMA (column names are CASE-SENSITIVE — always double-quote them):
{schema_desc}

USER QUESTION: "{user_message}"

CRITICAL RULES:
- Return ONLY the SQL query inside a ```sql code block
- Column names are CASE-SENSITIVE — you MUST double-quote them
- Table names do NOT need quoting (lowercase)
- JOIN tables using foreign keys where appropriate
- Add ORDER BY and LIMIT for readability
- Do NOT use write operations
- After the SQL block, add a one-sentence explanation"""

    sql_response, usage = await invoke_llm(prompt)
    all_usages.append(usage)
    generated_sql = _extract_sql(sql_response)

    if not generated_sql:
        return {
            "answer": f"I couldn't generate a valid SQL query.\n\n{sql_response}",
            "trace": {"type": "query_execution", "agent": "query_agent", "status": "no_sql",
                      "payload": {"query": user_message}, "sequence": 4},
        }

    sql_upper = generated_sql.strip().upper()
    if any(sql_upper.startswith(kw) for kw in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE"]):
        return {
            "answer": "I can only run read-only queries.",
            "trace": {"type": "query_execution", "agent": "query_agent", "status": "blocked",
                      "payload": {"sql": generated_sql}, "sequence": 4},
        }

    try:
        rows = await connector_instance.execute_query(generated_sql)
        rows = _make_serializable(rows)
    except Exception as e:
        return {
            "answer": f"SQL execution error: `{str(e)}`\n\n**SQL:**\n```sql\n{generated_sql}\n```",
            "trace": {"type": "query_execution", "agent": "query_agent", "status": "sql_error",
                      "payload": {"sql": generated_sql, "error": str(e)}, "sequence": 4},
        }

    if not rows:
        retry = await _sql_retry(user_message, connector_instance, generated_sql, schema_desc, all_usages)
        if retry:
            return retry
        explanation = sql_response.split("```")[-1].strip() if "```" in sql_response else ""
        return {
            "answer": f"The query returned no results.\n\n**SQL:**\n```sql\n{generated_sql}\n```\n{explanation}",
            "trace": {"type": "query_execution", "agent": "query_agent", "status": "empty",
                      "payload": {"sql": generated_sql}, "sequence": 4},
        }

    columns = list(rows[0].keys())
    total = len(rows)
    table_md = _format_results(columns, rows, total)

    explanation = ""
    parts = sql_response.split("```")
    if len(parts) >= 3:
        explanation = parts[-1].strip()

    response = f"{table_md}\n\n**SQL:**\n```sql\n{generated_sql}\n```"
    if explanation:
        response += f"\n\n{explanation}"

    return {
        "answer": response,
        "trace": {"type": "query_execution", "agent": "query_agent", "tool": "QueryResource",
                  "status": "success_fallback", "payload": {"sql": generated_sql, "row_count": total}, "sequence": 4},
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN ENTRY POINT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def query_agent(state: ADFAgentState) -> dict:
    """V3 query agent: entity extraction → per-entity hybrid search → rerank → resolve → SQL/RAG → response."""
    user_message = state["messages"][-1]["content"]
    all_usages = []

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
        # ── Step 3: Extract entities from user query ──
        entities = await _extract_entities(user_message, all_usages)

        trace_entities = {
            "type": "entity_extraction",
            "agent": "query_agent",
            "status": "success",
            "payload": {"entities": entities},
            "sequence": 2,
        }

        # ── Steps 4-7: Per-entity hybrid search + consolidate + rerank ──
        search_results = await _search_and_consolidate(entities, user_message)

        trace_search = {
            "type": "vector_search",
            "agent": "query_agent",
            "status": "success",
            "payload": {
                "search_queries": entities + [user_message],
                "tables_found": len(search_results["table_matches"]),
                "columns_found": len(search_results["column_matches"]),
                "values_found": len(search_results["value_matches"]),
                "chunks_found": len(search_results["chunk_matches"]),
                "resolved_tables": search_results["resolved_tables"],
            },
            "sequence": 3,
        }

        # ── Step 9: Resolve data type — structured SQL or unstructured chunks ──
        data_type = await _resolve_data_type(user_message, search_results, all_usages)

        # ── Steps 10-11: Execute based on resolved type ──
        if data_type == "structured":
            response = await _sql_path(user_message, connector_instance, search_results, all_usages)
        elif data_type == "unstructured":
            response = await _rag_path(user_message, search_results, all_usages)
        else:
            response = await _fallback_path(user_message, connector_instance, all_usages)

        await connector_instance.close()

        # ── Build trace and token tracking ──
        trace_events = [trace_entities, trace_search]
        if response.get("trace"):
            trace_events.append(response["trace"])

        result = {
            "final_response": response["answer"],
            "current_step": 3,
            "trace_events": trace_events,
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
                "latency_ms": u.latency_ms, "node": "query_agent",
            })
        result["token_count"] = {"input": total_input, "output": total_output, "cache": total_cache}
        result["llm_calls"] = llm_calls

        return result

    except Exception as e:
        try:
            await connector_instance.close()
        except Exception:
            pass
        error_msg = str(e)
        return {
            "final_response": f"I tried to process your query but encountered an error:\n\n`{error_msg}`\n\nPlease check that the connector is properly configured.",
            "current_step": 3,
            "trace_events": [{"type": "query", "agent": "query_agent", "status": "error",
                              "payload": {"error": error_msg}, "sequence": 3}],
        }
