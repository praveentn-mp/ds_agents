"""Data ingestion service — ingest data from connectors into DB tables and vector store."""

import csv
import io
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional, AsyncIterator
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.connector import Connector
from backend.models.sync_job import SyncJob
from backend.services.connector_service import _build_connector
from backend.config import settings

logger = logging.getLogger("adf.ingestion")

STRUCTURED_EXTENSIONS = {".csv", ".tsv", ".json", ".jsonl"}
UNSTRUCTURED_EXTENSIONS = {".txt", ".md", ".pdf", ".html", ".htm", ".doc", ".docx", ".log"}


def _sanitize_table_name(name: str) -> str:
    """Create a safe table name from a filename."""
    import re
    base = name.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", base).lower().strip("_")
    if not safe or safe[0].isdigit():
        safe = "t_" + safe
    return f"ingested_{safe}"


async def start_ingestion(
    db: AsyncSession,
    connector_id: UUID,
    user_id: UUID,
) -> AsyncIterator[dict]:
    """Ingest data from a connector. Yields SSE progress events."""
    result = await db.execute(select(Connector).where(Connector.id == connector_id))
    connector = result.scalar_one_or_none()
    if not connector:
        yield {"event": "error", "data": {"message": "Connector not found"}}
        return

    # Create sync job
    job = SyncJob(connector_id=connector_id, status="running")
    db.add(job)
    await db.flush()
    await db.refresh(job)

    yield {"event": "ingestion_start", "data": {
        "job_id": str(job.id),
        "connector_name": connector.name,
        "connector_type": connector.connector_type,
    }}

    try:
        instance = _build_connector(connector)

        if connector.connector_type == "postgres":
            async for event in _ingest_postgres(db, instance, connector, job):
                yield event
        elif connector.connector_type == "azure_blob":
            async for event in _ingest_blob(db, instance, connector, job):
                yield event
        elif connector.connector_type == "filesystem":
            async for event in _ingest_filesystem(db, instance, connector, job):
                yield event
        else:
            yield {"event": "error", "data": {"message": f"Unsupported connector type: {connector.connector_type}"}}
            job.status = "failed"
            job.error_message = f"Unsupported connector type: {connector.connector_type}"

        await instance.close()

        if job.status == "running":
            job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        connector.last_synced_at = datetime.now(timezone.utc)
        await db.flush()

        yield {"event": "ingestion_done", "data": {
            "job_id": str(job.id),
            "status": job.status,
            "rows_synced": job.rows_synced,
        }}

    except Exception as e:
        logger.error(f"Ingestion failed for connector {connector.name}: {e}")
        job.status = "failed"
        job.error_message = str(e)[:500]
        job.completed_at = datetime.now(timezone.utc)
        await db.flush()
        yield {"event": "error", "data": {"message": str(e), "job_id": str(job.id)}}


async def _ingest_postgres(db: AsyncSession, instance, connector: Connector, job: SyncJob):
    """For postgres connectors, discover schema and catalog tables. Data stays in source."""
    yield {"event": "ingestion_progress", "data": {
        "step": "Discovering schema from PostgreSQL...",
        "progress": 10,
    }}

    schema = await instance.discover_schema()
    tables = schema.get("tables", [])
    total_rows = 0

    for i, table in enumerate(tables):
        if table.get("schema") in ("pg_catalog", "information_schema"):
            continue
        table_name = table["name"]
        try:
            rows = await instance.execute_query(f"SELECT COUNT(*) as cnt FROM {table_name}")
            count = rows[0]["cnt"] if rows else 0
            total_rows += count
        except Exception:
            count = 0

        progress = 10 + int(80 * (i + 1) / max(len(tables), 1))
        yield {"event": "ingestion_progress", "data": {
            "step": f"Cataloged {table_name} ({count:,} rows)",
            "progress": min(progress, 90),
            "table": table_name,
            "row_count": count,
        }}

    job.rows_synced = total_rows
    yield {"event": "ingestion_progress", "data": {
        "step": f"Schema discovery complete. {len(tables)} tables, {total_rows:,} total rows ready for querying.",
        "progress": 100,
    }}


async def _ingest_blob(db: AsyncSession, instance, connector: Connector, job: SyncJob):
    """Download blobs, parse structured data into tables, index unstructured into vector store."""
    yield {"event": "ingestion_progress", "data": {
        "step": "Listing blobs in Azure Blob Storage...",
        "progress": 5,
    }}

    schema = await instance.discover_schema()
    all_blobs = []
    for container in schema.get("containers", []):
        for blob in container.get("blobs", []):
            all_blobs.append((container["name"], blob))

    if not all_blobs:
        yield {"event": "ingestion_progress", "data": {
            "step": "No blobs found in the container.",
            "progress": 100,
        }}
        return

    total = len(all_blobs)
    rows_synced = 0
    docs_indexed = 0

    for idx, (container_name, blob_info) in enumerate(all_blobs):
        blob_name = blob_info["name"]
        ext = "." + blob_name.rsplit(".", 1)[-1].lower() if "." in blob_name else ""

        progress = 5 + int(90 * (idx + 1) / total)

        yield {"event": "ingestion_progress", "data": {
            "step": f"Processing {blob_name}...",
            "progress": min(progress, 95),
            "file": blob_name,
        }}

        try:
            # Download blob content
            content = await _download_blob(instance, container_name, blob_name)

            if ext in STRUCTURED_EXTENSIONS:
                count = await _ingest_structured_content(db, content, blob_name, ext, connector.name)
                rows_synced += count
                yield {"event": "ingestion_progress", "data": {
                    "step": f"Loaded {blob_name} → {count:,} rows into database",
                    "progress": min(progress, 95),
                    "file": blob_name,
                    "row_count": count,
                }}
            elif ext in UNSTRUCTURED_EXTENSIONS:
                chunks = await _index_to_vector_store(db, content.decode("utf-8", errors="replace"), blob_name, connector.name)
                docs_indexed += 1
                yield {"event": "ingestion_progress", "data": {
                    "step": f"Indexed {blob_name} → {chunks} chunks for RAG",
                    "progress": min(progress, 95),
                    "file": blob_name,
                    "chunks": chunks,
                }}
            else:
                yield {"event": "ingestion_progress", "data": {
                    "step": f"Skipped {blob_name} (unsupported format: {ext})",
                    "progress": min(progress, 95),
                    "file": blob_name,
                }}
        except Exception as e:
            logger.warning(f"Failed to ingest blob {blob_name}: {e}")
            yield {"event": "ingestion_progress", "data": {
                "step": f"Failed: {blob_name} — {str(e)[:100]}",
                "progress": min(progress, 95),
                "file": blob_name,
                "error": str(e)[:200],
            }}

    job.rows_synced = rows_synced
    yield {"event": "ingestion_progress", "data": {
        "step": f"Done. {rows_synced:,} rows imported, {docs_indexed} documents indexed for RAG.",
        "progress": 100,
    }}


async def _ingest_filesystem(db: AsyncSession, instance, connector: Connector, job: SyncJob):
    """Read files, parse structured data into tables, index unstructured into vector store."""
    yield {"event": "ingestion_progress", "data": {
        "step": "Scanning filesystem...",
        "progress": 5,
    }}

    import os
    schema = await instance.discover_schema()
    all_files = []
    for directory in schema.get("directories", []):
        for f in directory.get("files", []):
            full_path = os.path.join(instance.base_path, directory["path"], f["name"])
            all_files.append((full_path, f["name"], f.get("extension", "")))

    if not all_files:
        yield {"event": "ingestion_progress", "data": {
            "step": "No files found.",
            "progress": 100,
        }}
        return

    total = len(all_files)
    rows_synced = 0
    docs_indexed = 0

    for idx, (full_path, filename, ext) in enumerate(all_files):
        ext = ext.lower()
        progress = 5 + int(90 * (idx + 1) / total)

        yield {"event": "ingestion_progress", "data": {
            "step": f"Processing {filename}...",
            "progress": min(progress, 95),
            "file": filename,
        }}

        try:
            with open(full_path, "rb") as fh:
                content = fh.read()

            if ext in STRUCTURED_EXTENSIONS:
                count = await _ingest_structured_content(db, content, filename, ext, connector.name)
                rows_synced += count
                yield {"event": "ingestion_progress", "data": {
                    "step": f"Loaded {filename} → {count:,} rows into database",
                    "progress": min(progress, 95),
                    "file": filename,
                    "row_count": count,
                }}
            elif ext in UNSTRUCTURED_EXTENSIONS:
                chunks = await _index_to_vector_store(db, content.decode("utf-8", errors="replace"), filename, connector.name)
                docs_indexed += 1
                yield {"event": "ingestion_progress", "data": {
                    "step": f"Indexed {filename} → {chunks} chunks for RAG",
                    "progress": min(progress, 95),
                    "file": filename,
                    "chunks": chunks,
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
                "progress": min(progress, 95),
                "error": str(e)[:200],
            }}

    job.rows_synced = rows_synced
    yield {"event": "ingestion_progress", "data": {
        "step": f"Done. {rows_synced:,} rows imported, {docs_indexed} documents indexed for RAG.",
        "progress": 100,
    }}


# ── Helpers ──

async def _download_blob(instance, container_name: str, blob_name: str) -> bytes:
    """Download a blob's content as bytes."""
    client = instance._get_client()
    container_client = client.get_container_client(container_name)
    blob_client = container_client.get_blob_client(blob_name)
    download = await blob_client.download_blob()
    return await download.readall()


async def _ingest_structured_content(
    db: AsyncSession, content: bytes, filename: str, ext: str, connector_name: str,
) -> int:
    """Parse CSV/JSON content and insert into a dynamically created table."""
    table_name = _sanitize_table_name(filename)

    if ext in (".csv", ".tsv"):
        delimiter = "\t" if ext == ".tsv" else ","
        text_content = content.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(text_content), delimiter=delimiter)
        rows = list(reader)
    elif ext == ".json":
        parsed = json.loads(content.decode("utf-8"))
        if isinstance(parsed, list):
            rows = parsed
        elif isinstance(parsed, dict) and any(isinstance(v, list) for v in parsed.values()):
            # Pick the first list value
            for v in parsed.values():
                if isinstance(v, list):
                    rows = v
                    break
        else:
            rows = [parsed]
    elif ext == ".jsonl":
        text_content = content.decode("utf-8", errors="replace")
        rows = [json.loads(line) for line in text_content.strip().split("\n") if line.strip()]
    else:
        return 0

    if not rows:
        return 0

    # Determine columns from first row
    columns = list(rows[0].keys())
    if not columns:
        return 0

    # Create table with TEXT columns (safe default)
    col_defs = ", ".join([f'"{c}" TEXT' for c in columns])
    create_sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            _id SERIAL PRIMARY KEY,
            _source TEXT DEFAULT '{connector_name}',
            _ingested_at TIMESTAMPTZ DEFAULT now(),
            {col_defs}
        )
    """
    await db.execute(text(create_sql))

    # Insert rows in batches
    col_list = ", ".join([f'"{c}"' for c in columns])
    inserted = 0
    for row in rows:
        placeholders = ", ".join([f":col{i}" for i in range(len(columns))])
        params = {f"col{i}": str(row.get(c, "")) for i, c in enumerate(columns)}
        insert_sql = f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})"
        await db.execute(text(insert_sql), params)
        inserted += 1

    await db.flush()
    return inserted


async def _index_to_vector_store(
    db: AsyncSession, text_content: str, source_uri: str, connector_name: str,
) -> int:
    """Chunk text and store into rag_documents + rag_chunks tables."""
    # Simple chunking: split by paragraphs, then combine into ~500 char chunks
    paragraphs = [p.strip() for p in text_content.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text_content[:2000]] if text_content.strip() else []

    chunks = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) > 500:
            if current:
                chunks.append(current)
            current = para
        else:
            current = (current + "\n\n" + para).strip()
    if current:
        chunks.append(current)

    if not chunks:
        return 0

    # Insert document record
    doc_result = await db.execute(
        text("INSERT INTO rag_documents (source_uri, title, metadata) VALUES (:uri, :title, :meta) RETURNING id"),
        {"uri": source_uri, "title": source_uri, "meta": json.dumps({"connector": connector_name})}
    )
    doc_id = doc_result.scalar_one()

    # Insert chunks (without embeddings for now — embedding requires LLM API)
    for i, chunk_text in enumerate(chunks):
        await db.execute(
            text("INSERT INTO rag_chunks (document_id, chunk_index, chunk_text) VALUES (:doc_id, :idx, :txt)"),
            {"doc_id": doc_id, "idx": i, "txt": chunk_text}
        )

    await db.flush()
    return len(chunks)


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
    """Get a summary of data available through this connector."""
    result = await db.execute(select(Connector).where(Connector.id == connector_id))
    connector = result.scalar_one_or_none()
    if not connector:
        return {"error": "Connector not found"}

    summary: dict = {
        "connector_id": str(connector_id),
        "connector_name": connector.name,
        "connector_type": connector.connector_type,
        "is_active": connector.is_active,
        "last_synced_at": str(connector.last_synced_at) if connector.last_synced_at else None,
        "tables": [],
        "documents": [],
    }

    # Check for ingested tables
    try:
        tables_result = await db.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name LIKE 'ingested_%' "
            "ORDER BY table_name"
        ))
        for row in tables_result:
            tname = row[0]
            count_result = await db.execute(text(f"SELECT COUNT(*) FROM {tname} WHERE _source = :src"), {"src": connector.name})
            count = count_result.scalar() or 0
            if count > 0:
                summary["tables"].append({"name": tname, "row_count": count})
    except Exception:
        pass

    # Check for RAG documents from this connector
    try:
        docs_result = await db.execute(text(
            "SELECT rd.id, rd.source_uri, rd.title, "
            "(SELECT COUNT(*) FROM rag_chunks rc WHERE rc.document_id = rd.id) as chunk_count "
            "FROM rag_documents rd "
            "WHERE rd.metadata->>'connector' = :name "
            "ORDER BY rd.created_at DESC"
        ), {"name": connector.name})
        for row in docs_result:
            summary["documents"].append({
                "id": str(row[0]),
                "source": row[1],
                "title": row[2],
                "chunks": row[3],
            })
    except Exception:
        pass

    # For postgres connectors, also show source tables
    if connector.connector_type == "postgres":
        try:
            instance = _build_connector(connector)
            schema = await instance.discover_schema()
            await instance.close()
            for t in schema.get("tables", []):
                if t.get("schema") in ("pg_catalog", "information_schema"):
                    continue
                summary["tables"].append({
                    "name": t["name"],
                    "column_count": len(t.get("columns", [])),
                    "source": "live",
                })
        except Exception:
            pass

    return summary
