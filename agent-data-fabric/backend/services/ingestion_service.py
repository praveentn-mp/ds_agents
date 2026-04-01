"""Data ingestion service v2 — LLM-enriched metadata, sentence-transformer embeddings, pgvector indices.

Architecture:
  Structured data → proper typed tables + LLM descriptions → embed table/column/values → 4 vector indices
  Unstructured data → chunk → embed → vec_chunk_index
"""

import csv
import io
import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional, AsyncIterator
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.connector import Connector
from backend.models.sync_job import SyncJob
from backend.services.connector_service import _build_connector
from backend.services.embedding_service import embed_texts, embed_single
from backend.agents.llm import invoke_llm
from backend.config import settings

logger = logging.getLogger("adf.ingestion")

STRUCTURED_EXTENSIONS = {".csv", ".tsv", ".json", ".jsonl"}
UNSTRUCTURED_EXTENSIONS = {".txt", ".md", ".pdf", ".html", ".htm", ".doc", ".docx", ".log"}

# Column types that should NOT be indexed for value-level search
NON_INDEXABLE_PATTERNS = [
    r"^id$", r"_id$", r"^uuid$", r"_uuid$", r"^pk$", r"^key$",
]


def _sanitize_table_name(name: str) -> str:
    """Create a safe table name from a filename."""
    base = name.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", base).lower().strip("_")
    if not safe or safe[0].isdigit():
        safe = "t_" + safe
    return f"ingested_{safe}"


def _infer_column_type(values: list[str]) -> str:
    """Infer a column's logical type from sample values.
    Returns: 'id', 'numeric', 'date', 'categorical', 'text', 'empty'
    """
    non_empty = [v for v in values if v and str(v).strip()]
    if not non_empty:
        return "empty"

    samples = non_empty[:200]

    # Check if UUID-like
    uuid_pat = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
    if all(uuid_pat.match(str(v).strip()) for v in samples):
        return "id"

    # Check numeric
    numeric_count = 0
    for v in samples:
        try:
            float(str(v).replace(",", ""))
            numeric_count += 1
        except ValueError:
            pass
    if numeric_count / len(samples) > 0.9:
        return "numeric"

    # Check date-like patterns
    date_patterns = [
        r"\d{4}-\d{2}-\d{2}", r"\d{2}/\d{2}/\d{4}", r"\d{2}-\d{2}-\d{4}",
    ]
    date_count = sum(1 for v in samples if any(re.search(p, str(v)) for p in date_patterns))
    if date_count / len(samples) > 0.8:
        return "date"

    # Categorical vs free text: if unique values < 50% of total and < 100 distinct
    unique = set(str(v).strip().lower() for v in samples)
    if len(unique) < min(50, len(samples) * 0.5):
        return "categorical"

    # Long text (avg > 50 chars) → unstructured
    avg_len = sum(len(str(v)) for v in samples) / len(samples)
    if avg_len > 100:
        return "text"

    return "categorical"


def _is_indexable(col_name: str, col_type: str) -> bool:
    """Should this column be indexed in the value vector index?"""
    if col_type in ("id", "empty"):
        return False
    for pat in NON_INDEXABLE_PATTERNS:
        if re.search(pat, col_name, re.I):
            return False
    return True


def _infer_pg_type(col_type: str) -> str:
    """Map inferred type to PostgreSQL column type."""
    return {
        "numeric": "NUMERIC",
        "date": "TIMESTAMPTZ",
        "id": "TEXT",
        "categorical": "TEXT",
        "text": "TEXT",
        "empty": "TEXT",
    }.get(col_type, "TEXT")


async def _save_llm_call(db: AsyncSession, usage, node: str = "ingestion", category: str = "ingestion"):
    """Save an LLM call to the llm_calls table for observability tracking."""
    if not usage:
        return
    try:
        await db.execute(
            text("""INSERT INTO llm_calls (category, model, tokens_input, tokens_output, tokens_cache, latency_ms, tool_calls)
                    VALUES (:cat, :model, :ti, :to, :tc, :lat, :tc_json)"""),
            {
                "cat": category,
                "model": usage.model or "unknown",
                "ti": usage.tokens_input, "to": usage.tokens_output,
                "tc": usage.tokens_cache, "lat": usage.latency_ms,
                "tc_json": json.dumps({"node": node}),
            }
        )
        await db.flush()
        logger.info(f"Saved LLM call for {node}: {usage.tokens_input}+{usage.tokens_output} tokens")
    except Exception as e:
        logger.warning(f"Failed to save LLM call: {e}")


async def start_ingestion(
    db: AsyncSession,
    connector_id: UUID,
    user_id: UUID,
    table_names: list[str] | None = None,
    file_names: list[str] | None = None,
) -> AsyncIterator[dict]:
    """Ingest data from a connector. Yields SSE progress events.
    
    For postgres connectors, table_names filters which tables to index.
    Uses its own DB sessions internally to avoid SSE session lifecycle issues.
    """
    from backend.database import async_session as session_factory

    # Load connector and create job in a short-lived session
    async with session_factory() as setup_db:
        result = await setup_db.execute(select(Connector).where(Connector.id == connector_id))
        connector = result.scalar_one_or_none()
        if not connector:
            yield {"event": "error", "data": {"message": "Connector not found"}}
            return

        job = SyncJob(connector_id=connector_id, status="running")
        setup_db.add(job)
        await setup_db.flush()
        await setup_db.refresh(job)
        job_id = job.id
        connector_name = connector.name
        connector_type = connector.connector_type
        await setup_db.commit()

    yield {"event": "ingestion_start", "data": {
        "job_id": str(job_id),
        "connector_name": connector_name,
        "connector_type": connector_type,
    }}

    try:
        # Reload connector fresh for building the instance
        async with session_factory() as fresh_db:
            result = await fresh_db.execute(select(Connector).where(Connector.id == connector_id))
            connector = result.scalar_one_or_none()
        instance = _build_connector(connector)

        if connector_type == "postgres":
            async for event in _ingest_postgres_wrapper(connector, instance, job_id, table_names):
                yield event
        elif connector_type == "azure_blob":
            async for event in _ingest_blob_wrapper(connector, instance, job_id, file_names):
                yield event
        elif connector_type == "filesystem":
            async for event in _ingest_filesystem_wrapper(connector, instance, job_id, file_names):
                yield event
        else:
            yield {"event": "error", "data": {"message": f"Unsupported connector type: {connector_type}"}}
            async with session_factory() as err_db:
                await err_db.execute(
                    text("UPDATE sync_jobs SET status = 'failed', error_message = :msg, completed_at = now() WHERE id = :jid"),
                    {"msg": f"Unsupported connector type: {connector_type}", "jid": str(job_id)}
                )
                await err_db.commit()

        await instance.close()

        # Finalize job
        async with session_factory() as final_db:
            await final_db.execute(
                text("UPDATE sync_jobs SET status = 'completed', completed_at = now() WHERE id = :jid AND status = 'running'"),
                {"jid": str(job_id)}
            )
            await final_db.execute(
                text("UPDATE connectors SET last_synced_at = now() WHERE id = :cid"),
                {"cid": str(connector_id)}
            )
            await final_db.commit()

        yield {"event": "ingestion_done", "data": {
            "job_id": str(job_id),
            "status": "completed",
            "rows_synced": 0,
        }}

    except Exception as e:
        logger.error(f"Ingestion failed for connector {connector_name}: {e}", exc_info=True)
        async with session_factory() as err_db:
            await err_db.execute(
                text("UPDATE sync_jobs SET status = 'failed', error_message = :msg, completed_at = now() WHERE id = :jid"),
                {"msg": str(e)[:500], "jid": str(job_id)}
            )
            await err_db.commit()
        yield {"event": "error", "data": {"message": str(e), "job_id": str(job_id)}}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POSTGRES CONNECTOR INGESTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _ingest_postgres_wrapper(connector: Connector, instance, job_id, table_names: list[str] | None = None):
    """Wrapper that creates its own DB session for postgres ingestion."""
    from backend.database import async_session as session_factory
    async with session_factory() as db:
        async for event in _ingest_postgres(db, instance, connector, job_id, table_names):
            yield event
        await db.commit()


async def _ingest_blob_wrapper(connector: Connector, instance, job_id, file_names: list[str] | None = None):
    """Wrapper that creates its own DB session for blob ingestion."""
    from backend.database import async_session as session_factory
    async with session_factory() as db:
        async for event in _ingest_blob(db, instance, connector, job_id, file_names):
            yield event
        await db.commit()


async def _ingest_filesystem_wrapper(connector: Connector, instance, job_id, file_names: list[str] | None = None):
    """Wrapper that creates its own DB session for filesystem ingestion."""
    from backend.database import async_session as session_factory
    async with session_factory() as db:
        async for event in _ingest_filesystem(db, instance, connector, job_id, file_names):
            yield event
        await db.commit()


async def _ingest_postgres(db: AsyncSession, instance, connector: Connector, job_id, table_names: list[str] | None = None):
    """For postgres, discover schema → build metadata → LLM descriptions → embeddings.
    
    If table_names is provided, only those tables are indexed.
    Otherwise, only b2b_* and ingested_* tables are indexed (no app tables).
    """
    yield {"event": "ingestion_progress", "data": {
        "step": "Discovering schema from PostgreSQL...",
        "progress": 5,
    }}

    # App tables to always exclude from indexing
    APP_TABLES = {
        "users", "roles", "connectors", "connector_schemas", "sync_jobs",
        "mcp_servers", "mcp_resources", "mcp_tools", "mcp_prompts",
        "custom_tools", "custom_tool_versions", "conversations", "messages",
        "execution_traces", "llm_calls", "sql_query_history",
        "rag_documents", "rag_chunks",
        "ingestion_metadata", "column_metadata",
        "vec_table_index", "vec_column_index", "vec_value_index", "vec_chunk_index",
    }

    schema = await instance.discover_schema()
    all_tables = [t for t in schema.get("tables", [])
                  if t.get("schema") not in ("pg_catalog", "information_schema")]

    if table_names:
        # User explicitly selected tables
        tables = [t for t in all_tables if t["name"] in table_names]
    else:
        # Default: exclude known app/system tables
        tables = [t for t in all_tables if t["name"] not in APP_TABLES]

    if not tables:
        yield {"event": "ingestion_progress", "data": {
            "step": "No user tables found.", "progress": 100,
        }}
        return

    total_rows = 0
    tables_indexed = 0
    columns_indexed = 0
    values_indexed = 0

    for i, table in enumerate(tables):
        table_name = table["name"]
        columns = table.get("columns", [])
        progress_base = 5 + int(85 * i / len(tables))

        yield {"event": "ingestion_progress", "data": {
            "step": f"Analyzing table: {table_name}...",
            "progress": progress_base,
            "table": table_name,
            "counts": {"tables": tables_indexed, "columns": columns_indexed, "values": values_indexed},
        }}

        # Get row count
        try:
            rows = await instance.execute_query(f"SELECT COUNT(*) as cnt FROM {table_name}")
            row_count = rows[0]["cnt"] if rows else 0
        except Exception:
            row_count = 0
        total_rows += row_count

        # Get sample data for type inference (5 rows)
        try:
            sample_rows = await instance.execute_query(
                f"SELECT * FROM {table_name} LIMIT 5"
            )
        except Exception:
            sample_rows = []

        # Build column analysis
        col_analysis = []
        for col_info in columns:
            col_name = col_info["name"]
            col_pg_type = col_info.get("type", "TEXT")
            sample_values = [str(r.get(col_name, "")) for r in sample_rows if r.get(col_name) is not None]

            # Get unique values for small cardinality columns
            categories = None
            value_range = None
            try:
                distinct_result = await instance.execute_query(
                    f"SELECT COUNT(DISTINCT \"{col_name}\") as cnt FROM {table_name}"
                )
                distinct_count = distinct_result[0]["cnt"] if distinct_result else 0

                if distinct_count <= 100 and distinct_count > 0:
                    cat_result = await instance.execute_query(
                        f"SELECT DISTINCT \"{col_name}\" FROM {table_name} WHERE \"{col_name}\" IS NOT NULL ORDER BY \"{col_name}\" LIMIT 100"
                    )
                    categories = [str(r[col_name]) for r in cat_result if r.get(col_name) is not None]
            except Exception:
                distinct_count = 0

            # Infer logical type
            all_samples = sample_values + (categories or [])
            inferred_type = _infer_column_type(all_samples) if all_samples else "empty"

            # Numeric range
            if inferred_type == "numeric":
                try:
                    range_result = await instance.execute_query(
                        f"SELECT MIN(\"{col_name}\") as mn, MAX(\"{col_name}\") as mx FROM {table_name}"
                    )
                    if range_result:
                        value_range = f"{range_result[0]['mn']} - {range_result[0]['mx']}"
                except Exception:
                    pass

            indexable = _is_indexable(col_name, inferred_type)

            col_analysis.append({
                "name": col_name,
                "pg_type": col_pg_type,
                "inferred_type": inferred_type,
                "sample_values": sample_values[:5],
                "categories": categories,
                "value_range": value_range,
                "is_indexable": indexable,
            })

        # ── LLM: Generate table + column descriptions ──
        yield {"event": "ingestion_progress", "data": {
            "step": f"Generating descriptions for {table_name}...",
            "progress": progress_base + 2,
            "table": table_name,
        }}

        table_desc, col_descriptions = await _generate_descriptions(
            table_name, col_analysis, row_count, db=db
        )

        # ── Store ingestion metadata ──
        meta_result = await db.execute(
            text("""INSERT INTO ingestion_metadata
                    (connector_id, source_file, table_name, table_description, row_count, column_count)
                    VALUES (:cid, :src, :tbl, :desc, :rows, :cols)
                    RETURNING id"""),
            {
                "cid": str(connector.id), "src": table_name,
                "tbl": table_name, "desc": table_desc,
                "rows": row_count, "cols": len(columns),
            }
        )
        ingestion_id = str(meta_result.scalar_one())

        # ── Store column metadata ──
        for ca in col_analysis:
            col_desc = col_descriptions.get(ca["name"], f"Column {ca['name']}")
            await db.execute(
                text("""INSERT INTO column_metadata
                        (ingestion_id, table_name, column_name, data_type, description,
                         sample_values, categories, value_range, is_indexable)
                        VALUES (:iid, :tbl, :col, :dtype, :desc, :samples, :cats, :vrange, :idx)"""),
                {
                    "iid": ingestion_id, "tbl": table_name, "col": ca["name"],
                    "dtype": ca["inferred_type"], "desc": col_desc,
                    "samples": ", ".join(ca["sample_values"][:5]),
                    "cats": ", ".join(ca["categories"][:50]) if ca["categories"] else None,
                    "vrange": ca["value_range"],
                    "idx": ca["is_indexable"],
                }
            )

        # ── Embed table description → vec_table_index ──
        yield {"event": "ingestion_progress", "data": {
            "step": f"Embedding table: {table_name}...",
            "progress": progress_base + 4,
            "table": table_name,
        }}

        table_embed_text = f"Table: {table_name}. {table_desc}"
        table_embedding = await embed_single(table_embed_text)
        await db.execute(
            text("""INSERT INTO vec_table_index
                    (ingestion_id, connector_id, table_name, description, embedding, metadata)
                    VALUES (:iid, :cid, :tbl, :desc, :emb, :meta)"""),
            {
                "iid": ingestion_id, "cid": str(connector.id),
                "tbl": table_name, "desc": table_desc,
                "emb": str(table_embedding),
                "meta": json.dumps({"row_count": row_count, "column_count": len(columns)}),
            }
        )
        tables_indexed += 1

        # ── Embed column descriptions → vec_column_index ──
        col_texts = []
        col_items = []
        for ca in col_analysis:
            col_desc = col_descriptions.get(ca["name"], f"Column {ca['name']}")
            embed_text = f"Table {table_name}, column {ca['name']}: {col_desc}. Type: {ca['inferred_type']}."
            if ca["categories"]:
                embed_text += f" Values: {', '.join(ca['categories'][:20])}."
            col_texts.append(embed_text)
            col_items.append(ca)

        if col_texts:
            col_embeddings = await embed_texts(col_texts)
            for ca, emb in zip(col_items, col_embeddings):
                col_desc = col_descriptions.get(ca["name"], f"Column {ca['name']}")
                await db.execute(
                    text("""INSERT INTO vec_column_index
                            (ingestion_id, connector_id, table_name, column_name, description, data_type, embedding, metadata)
                            VALUES (:iid, :cid, :tbl, :col, :desc, :dtype, :emb, :meta)"""),
                    {
                        "iid": ingestion_id, "cid": str(connector.id),
                        "tbl": table_name, "col": ca["name"],
                        "desc": col_desc, "dtype": ca["inferred_type"],
                        "emb": str(emb),
                        "meta": json.dumps({
                            "sample_values": ca["sample_values"][:5],
                            "is_indexable": ca["is_indexable"],
                        }),
                    }
                )
                columns_indexed += 1

        # ── Embed categorical values → vec_value_index ──
        value_texts = []
        value_items = []
        for ca in col_analysis:
            if not ca["is_indexable"] or not ca["categories"]:
                continue
            for val in ca["categories"][:100]:  # Cap at 100 values per column
                val_str = str(val).strip()
                if val_str:
                    value_texts.append(val_str)
                    value_items.append({"table": table_name, "column": ca["name"], "value": val_str})

        if value_texts:
            # Batch embed values (in chunks of 256)
            for batch_start in range(0, len(value_texts), 256):
                batch_texts = value_texts[batch_start:batch_start + 256]
                batch_items = value_items[batch_start:batch_start + 256]
                val_embeddings = await embed_texts(batch_texts)
                for vi, emb in zip(batch_items, val_embeddings):
                    await db.execute(
                        text("""INSERT INTO vec_value_index
                                (ingestion_id, connector_id, table_name, column_name, value_text, embedding, metadata)
                                VALUES (:iid, :cid, :tbl, :col, :val, :emb, :meta)"""),
                        {
                            "iid": ingestion_id, "cid": str(connector.id),
                            "tbl": vi["table"], "col": vi["column"],
                            "val": vi["value"], "emb": str(emb),
                            "meta": json.dumps({}),
                        }
                    )
                    values_indexed += 1

        await db.flush()

        yield {"event": "ingestion_progress", "data": {
            "step": f"Indexed {table_name}: {len(columns)} columns, {len(value_texts)} values",
            "progress": progress_base + 6,
            "table": table_name,
            "row_count": row_count,
            "counts": {"tables": tables_indexed, "columns": columns_indexed, "values": values_indexed},
        }}

    await db.execute(
        text("UPDATE sync_jobs SET rows_synced = :rows WHERE id = :jid"),
        {"rows": total_rows, "jid": str(job_id)}
    )
    await db.flush()
    yield {"event": "ingestion_progress", "data": {
        "step": f"Complete. {tables_indexed} tables, {columns_indexed} columns, {values_indexed} values indexed. {total_rows:,} total rows.",
        "progress": 100,
        "counts": {"tables": tables_indexed, "columns": columns_indexed, "values": values_indexed, "rows": total_rows},
    }}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BLOB CONNECTOR INGESTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _ingest_blob(db: AsyncSession, instance, connector: Connector, job_id, file_names: list[str] | None = None):
    """Download blobs → structured goes to tables+vectors, unstructured goes to chunk vectors."""
    yield {"event": "ingestion_progress", "data": {
        "step": "Listing blobs in Azure Blob Storage...", "progress": 5,
    }}

    schema = await instance.discover_schema()
    all_blobs = []
    for container in schema.get("containers", []):
        for blob in container.get("blobs", []):
            all_blobs.append((container["name"], blob))

    # Filter by selected file names if provided
    if file_names:
        file_names_set = set(file_names)
        all_blobs = [(c, b) for c, b in all_blobs if b["name"] in file_names_set]

    if not all_blobs:
        yield {"event": "ingestion_progress", "data": {
            "step": "No blobs found in the container.", "progress": 100,
        }}
        return

    total = len(all_blobs)
    rows_synced = 0
    tables_indexed = 0
    columns_indexed = 0
    values_indexed = 0
    chunks_indexed = 0

    for idx, (container_name, blob_info) in enumerate(all_blobs):
        blob_name = blob_info["name"]
        ext = "." + blob_name.rsplit(".", 1)[-1].lower() if "." in blob_name else ""
        progress = 5 + int(90 * (idx + 1) / total)

        yield {"event": "ingestion_progress", "data": {
            "step": f"Processing {blob_name}...", "progress": min(progress, 95),
            "file": blob_name,
            "counts": {"tables": tables_indexed, "columns": columns_indexed, "values": values_indexed, "chunks": chunks_indexed},
        }}

        try:
            content = await _download_blob(instance, container_name, blob_name)

            if ext in STRUCTURED_EXTENSIONS:
                result = await _ingest_structured_v2(db, content, blob_name, ext, connector)
                rows_synced += result["rows"]
                tables_indexed += result["tables"]
                columns_indexed += result["columns"]
                values_indexed += result["values"]
                yield {"event": "ingestion_progress", "data": {
                    "step": f"Loaded {blob_name} → {result['rows']:,} rows, {result['columns']} cols, {result['values']} values indexed",
                    "progress": min(progress, 95), "file": blob_name,
                    "counts": {"tables": tables_indexed, "columns": columns_indexed, "values": values_indexed, "chunks": chunks_indexed},
                }}
            elif ext in UNSTRUCTURED_EXTENSIONS:
                text_content = content.decode("utf-8", errors="replace")
                chunks = await _ingest_unstructured_v2(db, text_content, blob_name, connector)
                chunks_indexed += chunks
                yield {"event": "ingestion_progress", "data": {
                    "step": f"Indexed {blob_name} → {chunks} chunks for vector search",
                    "progress": min(progress, 95), "file": blob_name,
                    "counts": {"tables": tables_indexed, "columns": columns_indexed, "values": values_indexed, "chunks": chunks_indexed},
                }}
            else:
                yield {"event": "ingestion_progress", "data": {
                    "step": f"Skipped {blob_name} (unsupported format: {ext})",
                    "progress": min(progress, 95), "file": blob_name,
                }}

        except Exception as e:
            logger.warning(f"Failed to ingest blob {blob_name}: {e}")
            yield {"event": "ingestion_progress", "data": {
                "step": f"Failed: {blob_name} — {str(e)[:100]}",
                "progress": min(progress, 95), "file": blob_name, "error": str(e)[:200],
            }}

    await db.execute(
        text("UPDATE sync_jobs SET rows_synced = :rows WHERE id = :jid"),
        {"rows": rows_synced, "jid": str(job_id)}
    )
    await db.flush()
    yield {"event": "ingestion_progress", "data": {
        "step": f"Done. {rows_synced:,} rows, {tables_indexed} tables, {columns_indexed} columns, {values_indexed} values, {chunks_indexed} chunks indexed.",
        "progress": 100,
        "counts": {"tables": tables_indexed, "columns": columns_indexed, "values": values_indexed, "chunks": chunks_indexed, "rows": rows_synced},
    }}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FILESYSTEM CONNECTOR INGESTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _ingest_filesystem(db: AsyncSession, instance, connector: Connector, job_id, file_names: list[str] | None = None):
    """Read files from filesystem → structured tables+vectors, unstructured chunk vectors."""
    import os
    yield {"event": "ingestion_progress", "data": {
        "step": "Scanning filesystem...", "progress": 5,
    }}

    schema = await instance.discover_schema()
    all_files = []
    for directory in schema.get("directories", []):
        for f in directory.get("files", []):
            full_path = os.path.join(instance.base_path, directory["path"], f["name"])
            all_files.append((full_path, f["name"], f.get("extension", "")))

    # Filter by selected file names if provided
    if file_names:
        file_names_set = set(file_names)
        all_files = [(fp, fn, ext) for fp, fn, ext in all_files if fn in file_names_set]

    if not all_files:
        yield {"event": "ingestion_progress", "data": {
            "step": "No files found.", "progress": 100,
        }}
        return

    total = len(all_files)
    rows_synced = 0
    tables_indexed = 0
    columns_indexed = 0
    values_indexed = 0
    chunks_indexed = 0

    for idx, (full_path, filename, ext) in enumerate(all_files):
        ext = ext.lower()
        progress = 5 + int(90 * (idx + 1) / total)

        yield {"event": "ingestion_progress", "data": {
            "step": f"Processing {filename}...", "progress": min(progress, 95),
            "file": filename,
            "counts": {"tables": tables_indexed, "columns": columns_indexed, "values": values_indexed, "chunks": chunks_indexed},
        }}

        try:
            with open(full_path, "rb") as fh:
                content = fh.read()

            if ext in STRUCTURED_EXTENSIONS:
                result = await _ingest_structured_v2(db, content, filename, ext, connector)
                rows_synced += result["rows"]
                tables_indexed += result["tables"]
                columns_indexed += result["columns"]
                values_indexed += result["values"]
                yield {"event": "ingestion_progress", "data": {
                    "step": f"Loaded {filename} → {result['rows']:,} rows, {result['columns']} cols, {result['values']} values",
                    "progress": min(progress, 95), "file": filename,
                    "counts": {"tables": tables_indexed, "columns": columns_indexed, "values": values_indexed, "chunks": chunks_indexed},
                }}
            elif ext in UNSTRUCTURED_EXTENSIONS:
                text_content = content.decode("utf-8", errors="replace")
                chunks = await _ingest_unstructured_v2(db, text_content, filename, connector)
                chunks_indexed += chunks
                yield {"event": "ingestion_progress", "data": {
                    "step": f"Indexed {filename} → {chunks} chunks for vector search",
                    "progress": min(progress, 95), "file": filename,
                    "counts": {"tables": tables_indexed, "columns": columns_indexed, "values": values_indexed, "chunks": chunks_indexed},
                }}
            else:
                yield {"event": "ingestion_progress", "data": {
                    "step": f"Skipped {filename} (unsupported: {ext})",
                    "progress": min(progress, 95),
                }}
        except Exception as e:
            logger.warning(f"Failed to ingest file {filename}: {e}")
            yield {"event": "ingestion_progress", "data": {
                "step": f"Failed: {filename} — {str(e)[:100]}",
                "progress": min(progress, 95), "error": str(e)[:200],
            }}

    await db.execute(
        text("UPDATE sync_jobs SET rows_synced = :rows WHERE id = :jid"),
        {"rows": rows_synced, "jid": str(job_id)}
    )
    await db.flush()
    yield {"event": "ingestion_progress", "data": {
        "step": f"Done. {rows_synced:,} rows, {tables_indexed} tables, {columns_indexed} columns, {values_indexed} values, {chunks_indexed} chunks indexed.",
        "progress": 100,
        "counts": {"tables": tables_indexed, "columns": columns_indexed, "values": values_indexed, "chunks": chunks_indexed, "rows": rows_synced},
    }}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STRUCTURED DATA INGESTION (v2)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _ingest_structured_v2(
    db: AsyncSession, content: bytes, filename: str, ext: str, connector: Connector,
) -> dict:
    """Parse structured content → create typed table → LLM descriptions → embed → vector indices.
    Returns: {"rows": N, "tables": N, "columns": N, "values": N}
    """
    # Parse rows
    rows = _parse_structured_content(content, ext)
    if not rows:
        return {"rows": 0, "tables": 0, "columns": 0, "values": 0}

    columns = list(rows[0].keys())
    if not columns:
        return {"rows": 0, "tables": 0, "columns": 0, "values": 0}

    table_name = _sanitize_table_name(filename)

    # ── Analyze columns ──
    col_analysis = []
    for col_name in columns:
        all_values = [str(r.get(col_name, "")) for r in rows if r.get(col_name) is not None]
        inferred_type = _infer_column_type(all_values)

        categories = None
        value_range = None
        if inferred_type == "categorical":
            unique = sorted(set(v.strip() for v in all_values if v.strip()))[:100]
            categories = unique
        elif inferred_type == "numeric":
            try:
                nums = [float(str(v).replace(",", "")) for v in all_values if v.strip()]
                if nums:
                    value_range = f"{min(nums)} - {max(nums)}"
            except ValueError:
                pass

        indexable = _is_indexable(col_name, inferred_type)
        col_analysis.append({
            "name": col_name,
            "inferred_type": inferred_type,
            "sample_values": all_values[:5],
            "categories": categories,
            "value_range": value_range,
            "is_indexable": indexable,
        })

    # ── Create properly typed table ──
    col_defs = ", ".join([f'"{ca["name"]}" {_infer_pg_type(ca["inferred_type"])}' for ca in col_analysis])
    # Note: DDL statements (CREATE TABLE) don't support bind parameters in asyncpg.
    # Safely escape the source name by replacing single quotes.
    safe_source = connector.name.replace("'", "''")
    create_sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            _id SERIAL PRIMARY KEY,
            _source TEXT DEFAULT '{safe_source}',
            _ingested_at TIMESTAMPTZ DEFAULT now(),
            {col_defs}
        )
    """
    await db.execute(text(create_sql))

    # ── Insert rows ──
    col_list = ", ".join([f'"{ca["name"]}"' for ca in col_analysis])
    inserted = 0
    for row in rows:
        placeholders = ", ".join([f":col{i}" for i in range(len(columns))])
        params = {}
        for i, ca in enumerate(col_analysis):
            val = row.get(ca["name"], "")
            if ca["inferred_type"] == "numeric" and val:
                try:
                    params[f"col{i}"] = float(str(val).replace(",", ""))
                except ValueError:
                    params[f"col{i}"] = str(val)
            else:
                params[f"col{i}"] = str(val) if val else None
        insert_sql = f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})"
        await db.execute(text(insert_sql), params)
        inserted += 1
    await db.flush()

    # ── LLM descriptions ──
    table_desc, col_descriptions = await _generate_descriptions(table_name, col_analysis, inserted, db=db)

    # ── Store ingestion metadata ──
    meta_result = await db.execute(
        text("""INSERT INTO ingestion_metadata
                (connector_id, source_file, table_name, table_description, row_count, column_count)
                VALUES (:cid, :src, :tbl, :desc, :rows, :cols)
                RETURNING id"""),
        {
            "cid": str(connector.id), "src": filename,
            "tbl": table_name, "desc": table_desc,
            "rows": inserted, "cols": len(columns),
        }
    )
    ingestion_id = str(meta_result.scalar_one())

    # ── Store column metadata ──
    for ca in col_analysis:
        col_desc = col_descriptions.get(ca["name"], f"Column {ca['name']}")
        await db.execute(
            text("""INSERT INTO column_metadata
                    (ingestion_id, table_name, column_name, data_type, description,
                     sample_values, categories, value_range, is_indexable)
                    VALUES (:iid, :tbl, :col, :dtype, :desc, :samples, :cats, :vrange, :idx)"""),
            {
                "iid": ingestion_id, "tbl": table_name, "col": ca["name"],
                "dtype": ca["inferred_type"], "desc": col_desc,
                "samples": ", ".join(ca["sample_values"][:5]),
                "cats": ", ".join(ca["categories"][:50]) if ca["categories"] else None,
                "vrange": ca["value_range"],
                "idx": ca["is_indexable"],
            }
        )

    # ── Embed table → vec_table_index ──
    table_embed_text = f"Table: {table_name}. {table_desc}"
    table_embedding = await embed_single(table_embed_text)
    await db.execute(
        text("""INSERT INTO vec_table_index
                (ingestion_id, connector_id, table_name, description, embedding, metadata)
                VALUES (:iid, :cid, :tbl, :desc, :emb, :meta)"""),
        {
            "iid": ingestion_id, "cid": str(connector.id),
            "tbl": table_name, "desc": table_desc,
            "emb": str(table_embedding),
            "meta": json.dumps({"row_count": inserted, "source_file": filename}),
        }
    )
    tables_count = 1

    # ── Embed columns → vec_column_index ──
    col_texts = []
    col_items_for_embed = []
    for ca in col_analysis:
        col_desc = col_descriptions.get(ca["name"], f"Column {ca['name']}")
        embed_text = f"Table {table_name}, column {ca['name']}: {col_desc}. Type: {ca['inferred_type']}."
        if ca["categories"]:
            embed_text += f" Values: {', '.join(ca['categories'][:20])}."
        col_texts.append(embed_text)
        col_items_for_embed.append((ca, col_desc))

    columns_count = 0
    if col_texts:
        col_embeddings = await embed_texts(col_texts)
        for (ca, col_desc), emb in zip(col_items_for_embed, col_embeddings):
            await db.execute(
                text("""INSERT INTO vec_column_index
                        (ingestion_id, connector_id, table_name, column_name, description, data_type, embedding, metadata)
                        VALUES (:iid, :cid, :tbl, :col, :desc, :dtype, :emb, :meta)"""),
                {
                    "iid": ingestion_id, "cid": str(connector.id),
                    "tbl": table_name, "col": ca["name"],
                    "desc": col_desc, "dtype": ca["inferred_type"],
                    "emb": str(emb),
                    "meta": json.dumps({"sample_values": ca["sample_values"][:5]}),
                }
            )
            columns_count += 1

    # ── Embed values → vec_value_index ──
    value_texts = []
    value_items = []
    for ca in col_analysis:
        if not ca["is_indexable"] or not ca["categories"]:
            continue
        for val in ca["categories"][:100]:
            val_str = str(val).strip()
            if val_str:
                value_texts.append(val_str)
                value_items.append({"table": table_name, "column": ca["name"], "value": val_str})

    values_count = 0
    if value_texts:
        for batch_start in range(0, len(value_texts), 256):
            batch_t = value_texts[batch_start:batch_start + 256]
            batch_i = value_items[batch_start:batch_start + 256]
            val_embeddings = await embed_texts(batch_t)
            for vi, emb in zip(batch_i, val_embeddings):
                await db.execute(
                    text("""INSERT INTO vec_value_index
                            (ingestion_id, connector_id, table_name, column_name, value_text, embedding, metadata)
                            VALUES (:iid, :cid, :tbl, :col, :val, :emb, :meta)"""),
                    {
                        "iid": ingestion_id, "cid": str(connector.id),
                        "tbl": vi["table"], "col": vi["column"],
                        "val": vi["value"], "emb": str(emb),
                        "meta": json.dumps({}),
                    }
                )
                values_count += 1

    await db.flush()
    return {"rows": inserted, "tables": tables_count, "columns": columns_count, "values": values_count}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# UNSTRUCTURED DATA INGESTION (v2)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _ingest_unstructured_v2(
    db: AsyncSession, text_content: str, source_file: str, connector: Connector,
) -> int:
    """Chunk text → embed → store in vec_chunk_index. Returns chunk count."""
    chunks = _chunk_text(text_content)
    if not chunks:
        return 0

    # Also store in rag_documents for backwards compat
    doc_result = await db.execute(
        text("INSERT INTO rag_documents (source_uri, title, metadata) VALUES (:uri, :title, :meta) RETURNING id"),
        {"uri": source_file, "title": source_file, "meta": json.dumps({"connector": connector.name})}
    )
    doc_id = doc_result.scalar_one()

    # Embed all chunks
    chunk_embeddings = await embed_texts(chunks)

    for i, (chunk_text, embedding) in enumerate(zip(chunks, chunk_embeddings)):
        # Store in rag_chunks (legacy)
        await db.execute(
            text("INSERT INTO rag_chunks (document_id, chunk_index, chunk_text) VALUES (:doc_id, :idx, :txt)"),
            {"doc_id": doc_id, "idx": i, "txt": chunk_text}
        )

        # Store in vec_chunk_index (new vector search)
        await db.execute(
            text("""INSERT INTO vec_chunk_index
                    (connector_id, source_file, chunk_index, chunk_text, embedding, metadata)
                    VALUES (:cid, :src, :idx, :txt, :emb, :meta)"""),
            {
                "cid": str(connector.id), "src": source_file,
                "idx": i, "txt": chunk_text,
                "emb": str(embedding),
                "meta": json.dumps({"doc_id": str(doc_id)}),
            }
        )

    await db.flush()
    return len(chunks)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPER FUNCTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _parse_structured_content(content: bytes, ext: str) -> list[dict]:
    """Parse structured file content into list of dicts."""
    if ext in (".csv", ".tsv"):
        delimiter = "\t" if ext == ".tsv" else ","
        text_content = content.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(text_content), delimiter=delimiter)
        return list(reader)
    elif ext == ".json":
        parsed = json.loads(content.decode("utf-8"))
        if isinstance(parsed, list):
            return parsed
        elif isinstance(parsed, dict) and any(isinstance(v, list) for v in parsed.values()):
            for v in parsed.values():
                if isinstance(v, list):
                    return v
        else:
            return [parsed]
    elif ext == ".jsonl":
        text_content = content.decode("utf-8", errors="replace")
        return [json.loads(line) for line in text_content.strip().split("\n") if line.strip()]
    return []


def _chunk_text(text_content: str, max_chunk_size: int = 500) -> list[str]:
    """Smart chunking: split by paragraphs, combine to ~500 char chunks."""
    paragraphs = [p.strip() for p in text_content.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text_content[:2000]] if text_content.strip() else []

    chunks = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) > max_chunk_size:
            if current:
                chunks.append(current)
            current = para
        else:
            current = (current + "\n\n" + para).strip()
    if current:
        chunks.append(current)
    return chunks


async def _generate_descriptions(
    table_name: str, col_analysis: list[dict], row_count: int,
    db: AsyncSession = None,
) -> tuple[str, dict[str, str]]:
    """Use LLM to generate a table-level description and per-column descriptions.
    Returns (table_description, {column_name: description}).
    If db is passed, saves the LLM call for observability.
    """
    col_summary = ""
    for ca in col_analysis:
        samples = ", ".join(ca["sample_values"][:3]) if ca["sample_values"] else "N/A"
        col_summary += f"  - {ca['name']} (type: {ca['inferred_type']}, samples: {samples})\n"

    prompt = f"""Analyze this database table and provide concise, business-friendly descriptions.

Table: {table_name}
Row count: {row_count}
Columns:
{col_summary}

Respond with ONLY valid JSON:
{{
  "table_description": "one sentence describing what this table contains",
  "columns": {{
    "column_name": "what this column represents"
  }}
}}

Be concise. Each description should be a single sentence."""

    try:
        content, usage = await invoke_llm(prompt)
        # Track LLM call for observability
        if db:
            await _save_llm_call(db, usage, node=f"ingestion_describe_{table_name}")
        content = content.strip()
        # Extract JSON from potential code blocks
        if "```" in content:
            parts = content.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    content = part
                    break
        parsed = json.loads(content)
        table_desc = parsed.get("table_description", f"Table {table_name}")
        col_descs = parsed.get("columns", {})
        return table_desc, col_descs
    except Exception as e:
        logger.warning(f"LLM description generation failed for {table_name}: {e}")
        # Fallback descriptions
        table_desc = f"Data table {table_name} with {row_count} rows and {len(col_analysis)} columns."
        col_descs = {ca["name"]: f"Column {ca['name']} ({ca['inferred_type']})" for ca in col_analysis}
        return table_desc, col_descs


async def _download_blob(instance, container_name: str, blob_name: str) -> bytes:
    """Download a blob's content as bytes."""
    client = instance._get_client()
    container_client = client.get_container_client(container_name)
    blob_client = container_client.get_blob_client(blob_name)
    download = await blob_client.download_blob()
    return await download.readall()


async def get_ingestion_status(db: AsyncSession, connector_id: UUID) -> dict:
    """Get the latest ingestion job status for a connector."""
    result = await db.execute(
        select(SyncJob)
        .where(SyncJob.connector_id == connector_id)
        .order_by(SyncJob.started_at.desc())
        .limit(1)
    )
    job = result.scalar_one_or_none()
    if not job:
        return {"status": "never_run", "connector_id": str(connector_id)}
    return {
        "job_id": str(job.id),
        "status": job.status,
        "rows_synced": job.rows_synced,
        "error_message": job.error_message,
        "started_at": str(job.started_at) if job.started_at else None,
        "completed_at": str(job.completed_at) if job.completed_at else None,
        "connector_id": str(connector_id),
    }


async def get_connector_data_summary(db: AsyncSession, connector_id: UUID) -> dict:
    """Get summary of ingested data for a connector including vector index counts."""
    # Get ingestion metadata
    result = await db.execute(
        text("""SELECT id, source_file, table_name, table_description, row_count, column_count, created_at
                FROM ingestion_metadata WHERE connector_id = :cid ORDER BY created_at DESC"""),
        {"cid": str(connector_id)}
    )
    ingestions = [dict(r._mapping) for r in result.fetchall()]

    # Get vector index counts
    table_count = await db.execute(
        text("SELECT COUNT(*) FROM vec_table_index WHERE connector_id = :cid"),
        {"cid": str(connector_id)}
    )
    column_count = await db.execute(
        text("SELECT COUNT(*) FROM vec_column_index WHERE connector_id = :cid"),
        {"cid": str(connector_id)}
    )
    value_count = await db.execute(
        text("SELECT COUNT(*) FROM vec_value_index WHERE connector_id = :cid"),
        {"cid": str(connector_id)}
    )
    chunk_count = await db.execute(
        text("SELECT COUNT(*) FROM vec_chunk_index WHERE connector_id = :cid"),
        {"cid": str(connector_id)}
    )

    return {
        "connector_id": str(connector_id),
        "ingestions": [{
            "id": str(i["id"]),
            "source_file": i["source_file"],
            "table_name": i["table_name"],
            "table_description": i["table_description"],
            "row_count": i["row_count"],
            "column_count": i["column_count"],
            "created_at": str(i["created_at"]),
        } for i in ingestions],
        "vector_counts": {
            "tables": table_count.scalar_one(),
            "columns": column_count.scalar_one(),
            "values": value_count.scalar_one(),
            "chunks": chunk_count.scalar_one(),
        },
        "total_rows": sum(i["row_count"] or 0 for i in ingestions),
    }


async def delete_connector_data(db: AsyncSession, connector_id: UUID) -> dict:
    """Delete all ingested data and vector indices for a connector."""
    cid = str(connector_id)
    # Delete vector indices
    await db.execute(text("DELETE FROM vec_value_index WHERE connector_id = :cid"), {"cid": cid})
    await db.execute(text("DELETE FROM vec_column_index WHERE connector_id = :cid"), {"cid": cid})
    await db.execute(text("DELETE FROM vec_table_index WHERE connector_id = :cid"), {"cid": cid})
    await db.execute(text("DELETE FROM vec_chunk_index WHERE connector_id = :cid"), {"cid": cid})

    # Get ingested table names to drop
    result = await db.execute(
        text("SELECT table_name FROM ingestion_metadata WHERE connector_id = :cid"), {"cid": cid}
    )
    table_names = [r[0] for r in result.fetchall()]

    # Delete metadata (cascades to column_metadata)
    await db.execute(text("DELETE FROM ingestion_metadata WHERE connector_id = :cid"), {"cid": cid})

    # Drop ingested tables
    dropped = []
    for tbl in table_names:
        if tbl.startswith("ingested_"):
            await db.execute(text(f"DROP TABLE IF EXISTS {tbl}"))
            dropped.append(tbl)

    await db.flush()
    return {"deleted_tables": dropped, "connector_id": cid}


async def reindex_connector(db: AsyncSession, connector_id: UUID, user_id: UUID) -> AsyncIterator[dict]:
    """Delete existing index data and re-run ingestion for a connector."""
    from backend.database import async_session as session_factory

    # Use own session to avoid SSE lifecycle issues
    async with session_factory() as own_db:
        await delete_connector_data(own_db, connector_id)
        await own_db.commit()

    yield {"event": "reindex_start", "data": {"message": "Cleared existing index data. Re-ingesting..."}}

    # Re-run ingestion
    async for event in start_ingestion(db, connector_id, user_id):
        yield event
