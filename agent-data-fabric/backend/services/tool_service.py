"""Custom tool service — CRUD, execution, versioning, AI generation."""

import json
import time
from decimal import Decimal
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from RestrictedPython import compile_restricted, safe_globals

from backend.models.custom_tool import CustomTool
from backend.models.tool_version import ToolVersion
from backend.models.mcp_tool import MCPTool


def _make_serializable(obj):
    """Recursively convert non-JSON-serializable types."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(i) for i in obj]
    if isinstance(obj, UUID):
        return str(obj)
    return obj


async def list_tools(db: AsyncSession) -> list[CustomTool]:
    result = await db.execute(select(CustomTool).order_by(CustomTool.created_at.desc()))
    return list(result.scalars().all())


async def get_tool(db: AsyncSession, tool_id: UUID) -> Optional[CustomTool]:
    result = await db.execute(select(CustomTool).where(CustomTool.id == tool_id))
    return result.scalar_one_or_none()


async def create_tool(db: AsyncSession, data: dict, owner_id: Optional[UUID] = None) -> CustomTool:
    tool = CustomTool(
        name=data["name"],
        description=data.get("description"),
        code=data["code"],
        input_schema=data.get("input_schema", {}),
        owner_id=owner_id,
    )
    db.add(tool)
    await db.flush()
    await db.refresh(tool)

    # Save initial version
    version = ToolVersion(
        tool_id=tool.id,
        version=1,
        code=data["code"],
        input_schema=data.get("input_schema", {}),
        created_by=owner_id,
    )
    db.add(version)

    # Auto-register as MCP tool (idempotent — update if exists)
    existing_mcp = await db.execute(
        select(MCPTool).where(MCPTool.name == tool.name, MCPTool.source_type == "custom_tool")
    )
    mcp_row = existing_mcp.scalar_one_or_none()
    if mcp_row:
        mcp_row.description = tool.description
        mcp_row.input_schema = tool.input_schema
        mcp_row.source_id = tool.id
        mcp_row.is_active = True
    else:
        mcp_tool = MCPTool(
            name=tool.name,
            description=tool.description,
            input_schema=tool.input_schema,
            source_type="custom_tool",
            source_id=tool.id,
        )
        db.add(mcp_tool)
    await db.flush()
    return tool


async def update_tool(db: AsyncSession, tool_id: UUID, data: dict, user_id: Optional[UUID] = None) -> Optional[CustomTool]:
    result = await db.execute(select(CustomTool).where(CustomTool.id == tool_id))
    tool = result.scalar_one_or_none()
    if not tool:
        return None

    if data.get("code"):
        tool.code = data["code"]
        tool.current_version += 1
        version = ToolVersion(
            tool_id=tool.id,
            version=tool.current_version,
            code=data["code"],
            input_schema=data.get("input_schema", tool.input_schema),
            created_by=user_id,
        )
        db.add(version)

    if data.get("description") is not None:
        tool.description = data["description"]
    if data.get("input_schema") is not None:
        tool.input_schema = data["input_schema"]
    if data.get("is_active") is not None:
        tool.is_active = data["is_active"]

    await db.flush()
    await db.refresh(tool)
    return tool


async def execute_tool(db: AsyncSession, tool_id: UUID, arguments: dict) -> dict:
    tool = await get_tool(db, tool_id)
    if not tool:
        return {"success": False, "error": "Tool not found", "duration_ms": 0}

    start = time.monotonic()
    try:
        # Sandboxed execution
        restricted_globals = safe_globals.copy()
        restricted_globals["_getattr_"] = getattr
        restricted_globals["_getitem_"] = lambda obj, key: obj[key]
        restricted_globals["__builtins__"]["__import__"] = None  # block imports
        # Allow common builtins inside sandbox
        for fn in (float, int, str, list, dict, len, range, sorted, min, max, round, abs, bool, tuple, enumerate, zip):
            restricted_globals["__builtins__"][fn.__name__] = fn

        byte_code = compile_restricted(tool.code, '<custom_tool>', 'exec')
        local_ns = {"arguments": arguments}
        exec(byte_code, restricted_globals, local_ns)

        result = local_ns.get("result", local_ns.get("output", None))

        # If tool produced a SQL query, execute it against the DB
        if isinstance(result, dict) and "sql" in result and isinstance(result["sql"], str):
            sql_str = result["sql"]
            sql_params = result.get("params", {})
            try:
                db_result = await db.execute(text(sql_str), sql_params)
                rows = db_result.fetchall()
                columns = list(db_result.keys())

                # Retry with ILIKE if exact match returned empty and query has = 'value'
                if not rows and "= '" in sql_str:
                    import re
                    # Try 1: ILIKE with the original value
                    ilike_sql = re.sub(r"""= '([^']+)'""", r"ILIKE '%\1%'", sql_str)
                    if ilike_sql != sql_str:
                        try:
                            db_result2 = await db.execute(text(ilike_sql), sql_params)
                            rows2 = db_result2.fetchall()
                            if rows2:
                                rows = rows2
                                columns = list(db_result2.keys())
                                sql_str = ilike_sql
                        except Exception:
                            pass

                    # Try 2: If still empty, remove the WHERE clause to show all data
                    if not rows:
                        no_where = re.sub(r"\s+WHERE\s+.*?(?=ORDER|GROUP|LIMIT|$)", " ", sql_str, flags=re.IGNORECASE | re.DOTALL).strip()
                        if no_where != sql_str:
                            # Add LIMIT if not present
                            if "LIMIT" not in no_where.upper():
                                no_where += " LIMIT 20"
                            try:
                                db_result3 = await db.execute(text(no_where), {})
                                rows3 = db_result3.fetchall()
                                if rows3:
                                    rows = rows3
                                    columns = list(db_result3.keys())
                                    sql_str = no_where
                            except Exception:
                                pass

                result = {
                    "data": [dict(zip(columns, row)) for row in rows],
                    "columns": columns,
                    "row_count": len(rows),
                    "sql": sql_str,
                }
            except Exception as sql_err:
                result = {"sql_error": str(sql_err), "sql": sql_str}

        # Ensure all values are JSON-serializable
        result = _make_serializable(result)

        duration = int((time.monotonic() - start) * 1000)
        return {"success": True, "result": result, "duration_ms": duration}
    except Exception as e:
        duration = int((time.monotonic() - start) * 1000)
        return {"success": False, "error": str(e), "duration_ms": duration}


async def get_tool_versions(db: AsyncSession, tool_id: UUID) -> list[ToolVersion]:
    result = await db.execute(
        select(ToolVersion).where(ToolVersion.tool_id == tool_id).order_by(ToolVersion.version.desc())
    )
    return list(result.scalars().all())


async def generate_tool(db: AsyncSession, description: str, connector_id: Optional[str] = None) -> dict:
    """Agent-assisted tool generation: identify tables → generate SQL → generate tool code.

    Returns dict with: name, description, sql, code, input_schema, matched_tables, explanation
    """
    from backend.agents.llm import invoke_llm
    from backend.services.search_service import hybrid_search, get_table_schema_from_metadata

    # Step 1: Search for relevant tables/columns
    search_response = await hybrid_search(
        query=description,
        db=db,
        top_k=10,
        min_score=0.2,
        connector_id=connector_id,
    )

    matched_tables = search_response.resolved_tables[:5]

    # Step 2: Get schema for matched tables
    schema_desc = await get_table_schema_from_metadata(db, matched_tables)

    if not schema_desc:
        # Fallback: try live schema
        schema_desc = "No indexed tables found. Available tables:\n"
        result = await db.execute(
            text("SELECT table_name FROM ingestion_metadata ORDER BY created_at DESC LIMIT 10")
        )
        for row in result.fetchall():
            schema_desc += f"  - {row[0]}\n"

    # Step 3: Build value hints
    value_hints = ""
    if search_response.resolved_values:
        value_hints = "\nKNOWN VALUES:\n"
        for key, vals in search_response.resolved_values.items():
            value_hints += f"  - {key}: {', '.join(repr(v) for v in vals[:5])}\n"

    # Step 4: Ask LLM to generate tool spec
    prompt = f"""You are a tool builder. Given the user's description and available database schema, generate a reusable data tool.

USER REQUEST: "{description}"

DATABASE SCHEMA (column names are CASE-SENSITIVE — double-quote them in SQL):
{schema_desc}
{value_hints}

Generate a complete tool specification as JSON:
{{
  "name": "snake_case_tool_name",
  "description": "One sentence describing what this tool does",
  "sql": "The SQL query this tool runs (use double-quoted column names, parameterized with {{param_name}} placeholders for user inputs)",
  "code": "Python code that takes `arguments` dict and sets `result`. The code should format the SQL, execute it via the `execute_sql` helper, and return results.",
  "input_schema": {{
    "param_name": {{"type": "string", "description": "what this param is"}}
  }},
  "explanation": "Brief explanation of what was built and why"
}}

IMPORTANT CODE RULES:
- The tool code MUST use this pattern:
  ```
  sql = "SELECT ... FROM table WHERE \\"Column\\" = '{{value}}'".format(value=arguments.get("param", "default"))
  result = {{"sql": sql, "description": "what this query does"}}
  ```
- Do NOT use any imports
- Keep it simple — just format SQL and return it as the result
- The agent will execute the SQL separately
- For text/string filters, prefer ILIKE over exact = for flexibility
- Defaults for parameters MUST come from KNOWN VALUES above (never guess country codes, statuses, etc.)
- If no known values, use a broad default that returns results (e.g., no WHERE clause)

Return ONLY valid JSON, no markdown."""

    response, usage = await invoke_llm(prompt)

    try:
        content = response.strip()
        if "```" in content:
            parts = content.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    content = part
                    break
        spec = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return {
            "success": False,
            "error": "Failed to generate valid tool specification",
            "raw_response": response,
            "matched_tables": matched_tables,
        }

    return {
        "success": True,
        "name": spec.get("name", "unnamed_tool"),
        "description": spec.get("description", description),
        "sql": spec.get("sql", ""),
        "code": spec.get("code", ""),
        "input_schema": spec.get("input_schema", {}),
        "explanation": spec.get("explanation", ""),
        "matched_tables": matched_tables,
        "tokens_used": {"input": usage.tokens_input, "output": usage.tokens_output},
    }
