"""Hybrid vector search service — search across all 4 vector indices with reranking.

Search flow:
  1. Embed user query with sentence-transformers
  2. Search vec_table_index, vec_column_index, vec_value_index, vec_chunk_index in parallel
  3. Merge + rerank results by cosine similarity
  4. Return unified ranked results
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.embedding_service import embed_single
from backend.database import async_session

logger = logging.getLogger("adf.search")


@dataclass
class SearchResult:
    """A single search result from any vector index."""
    index_type: str  # "table", "column", "value", "chunk"
    score: float
    table_name: Optional[str] = None
    column_name: Optional[str] = None
    value_text: Optional[str] = None
    description: Optional[str] = None
    data_type: Optional[str] = None
    chunk_text: Optional[str] = None
    source_file: Optional[str] = None
    connector_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "index_type": self.index_type,
            "score": round(self.score, 4),
            "table_name": self.table_name,
            "column_name": self.column_name,
            "value_text": self.value_text,
            "description": self.description,
            "data_type": self.data_type,
            "chunk_text": self.chunk_text,
            "source_file": self.source_file,
            "connector_id": self.connector_id,
            "metadata": self.metadata,
        }


@dataclass
class SearchResponse:
    """Aggregated search results across all indices."""
    query: str
    results: list[SearchResult]
    table_matches: list[SearchResult] = field(default_factory=list)
    column_matches: list[SearchResult] = field(default_factory=list)
    value_matches: list[SearchResult] = field(default_factory=list)
    chunk_matches: list[SearchResult] = field(default_factory=list)

    # Resolved entities for SQL generation
    resolved_tables: list[str] = field(default_factory=list)
    resolved_columns: dict = field(default_factory=dict)  # {table: [columns]}
    resolved_values: dict = field(default_factory=dict)   # {table.column: [values]}

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "total_results": len(self.results),
            "results": [r.to_dict() for r in self.results[:20]],
            "table_matches": [r.to_dict() for r in self.table_matches],
            "column_matches": [r.to_dict() for r in self.column_matches],
            "value_matches": [r.to_dict() for r in self.value_matches],
            "chunk_matches": [r.to_dict() for r in self.chunk_matches],
            "resolved_tables": self.resolved_tables,
            "resolved_columns": self.resolved_columns,
            "resolved_values": self.resolved_values,
        }


async def hybrid_search(
    query: str,
    db: AsyncSession,
    top_k: int = 10,
    min_score: float = 0.3,
    connector_id: Optional[str] = None,
) -> SearchResponse:
    """Execute hybrid search across all 4 vector indices.

    Args:
        query: User's natural language query
        db: Database session
        top_k: Max results per index
        min_score: Minimum cosine similarity threshold
        connector_id: Optional filter by connector
    """
    # Step 1: Embed the query
    query_embedding = await embed_single(query)
    emb_str = str(query_embedding)

    # Step 2: Search all 4 indices
    table_results = await _search_table_index(db, emb_str, top_k, min_score, connector_id)
    column_results = await _search_column_index(db, emb_str, top_k, min_score, connector_id)
    value_results = await _search_value_index(db, emb_str, top_k, min_score, connector_id)
    chunk_results = await _search_chunk_index(db, emb_str, top_k, min_score, connector_id)

    # Step 3: Merge and sort by score
    all_results = table_results + column_results + value_results + chunk_results
    all_results.sort(key=lambda r: r.score, reverse=True)

    # Step 4: Resolve entities
    resolved_tables = list(dict.fromkeys(
        r.table_name for r in (table_results + column_results + value_results)
        if r.table_name
    ))

    resolved_columns: dict[str, list[str]] = {}
    for r in column_results:
        if r.table_name and r.column_name:
            resolved_columns.setdefault(r.table_name, [])
            if r.column_name not in resolved_columns[r.table_name]:
                resolved_columns[r.table_name].append(r.column_name)

    resolved_values: dict[str, list[str]] = {}
    for r in value_results:
        if r.table_name and r.column_name and r.value_text:
            key = f"{r.table_name}.{r.column_name}"
            resolved_values.setdefault(key, [])
            if r.value_text not in resolved_values[key]:
                resolved_values[key].append(r.value_text)

    response = SearchResponse(
        query=query,
        results=all_results,
        table_matches=table_results,
        column_matches=column_results,
        value_matches=value_results,
        chunk_matches=chunk_results,
        resolved_tables=resolved_tables,
        resolved_columns=resolved_columns,
        resolved_values=resolved_values,
    )

    logger.info(
        f"Hybrid search for '{query}': "
        f"{len(table_results)} tables, {len(column_results)} columns, "
        f"{len(value_results)} values, {len(chunk_results)} chunks"
    )
    return response


async def _search_table_index(
    db: AsyncSession, emb_str: str, top_k: int, min_score: float, connector_id: Optional[str],
) -> list[SearchResult]:
    """Search vec_table_index by cosine similarity."""
    where_clause = "WHERE 1=1"
    params: dict = {"emb": emb_str, "k": top_k, "min_score": min_score}
    if connector_id:
        where_clause += " AND connector_id = :cid"
        params["cid"] = connector_id

    result = await db.execute(
        text(f"""
            SELECT table_name, description, CAST(connector_id AS text) as connector_id, metadata,
                   1 - (embedding <=> CAST(:emb AS vector)) as score
            FROM vec_table_index
            {where_clause}
            ORDER BY embedding <=> CAST(:emb AS vector)
            LIMIT :k
        """),
        params,
    )

    results = []
    for row in result.fetchall():
        score = float(row.score)
        if score >= min_score:
            meta = row.metadata if isinstance(row.metadata, dict) else {}
            results.append(SearchResult(
                index_type="table",
                score=score,
                table_name=row.table_name,
                description=row.description,
                connector_id=row.connector_id,
                metadata=meta,
            ))
    return results


async def _search_column_index(
    db: AsyncSession, emb_str: str, top_k: int, min_score: float, connector_id: Optional[str],
) -> list[SearchResult]:
    """Search vec_column_index by cosine similarity."""
    where_clause = "WHERE 1=1"
    params: dict = {"emb": emb_str, "k": top_k, "min_score": min_score}
    if connector_id:
        where_clause += " AND connector_id = :cid"
        params["cid"] = connector_id

    result = await db.execute(
        text(f"""
            SELECT table_name, column_name, description, data_type,
                   CAST(connector_id AS text) as connector_id, metadata,
                   1 - (embedding <=> CAST(:emb AS vector)) as score
            FROM vec_column_index
            {where_clause}
            ORDER BY embedding <=> CAST(:emb AS vector)
            LIMIT :k
        """),
        params,
    )

    results = []
    for row in result.fetchall():
        score = float(row.score)
        if score >= min_score:
            meta = row.metadata if isinstance(row.metadata, dict) else {}
            results.append(SearchResult(
                index_type="column",
                score=score,
                table_name=row.table_name,
                column_name=row.column_name,
                description=row.description,
                data_type=row.data_type,
                connector_id=row.connector_id,
                metadata=meta,
            ))
    return results


async def _search_value_index(
    db: AsyncSession, emb_str: str, top_k: int, min_score: float, connector_id: Optional[str],
) -> list[SearchResult]:
    """Search vec_value_index by cosine similarity."""
    where_clause = "WHERE 1=1"
    params: dict = {"emb": emb_str, "k": top_k, "min_score": min_score}
    if connector_id:
        where_clause += " AND connector_id = :cid"
        params["cid"] = connector_id

    result = await db.execute(
        text(f"""
            SELECT table_name, column_name, value_text,
                   CAST(connector_id AS text) as connector_id, metadata,
                   1 - (embedding <=> CAST(:emb AS vector)) as score
            FROM vec_value_index
            {where_clause}
            ORDER BY embedding <=> CAST(:emb AS vector)
            LIMIT :k
        """),
        params,
    )

    results = []
    for row in result.fetchall():
        score = float(row.score)
        if score >= min_score:
            meta = row.metadata if isinstance(row.metadata, dict) else {}
            results.append(SearchResult(
                index_type="value",
                score=score,
                table_name=row.table_name,
                column_name=row.column_name,
                value_text=row.value_text,
                connector_id=row.connector_id,
                metadata=meta,
            ))
    return results


async def _search_chunk_index(
    db: AsyncSession, emb_str: str, top_k: int, min_score: float, connector_id: Optional[str],
) -> list[SearchResult]:
    """Search vec_chunk_index by cosine similarity."""
    where_clause = "WHERE 1=1"
    params: dict = {"emb": emb_str, "k": top_k, "min_score": min_score}
    if connector_id:
        where_clause += " AND connector_id = :cid"
        params["cid"] = connector_id

    result = await db.execute(
        text(f"""
            SELECT source_file, chunk_text, CAST(connector_id AS text) as connector_id, metadata,
                   1 - (embedding <=> CAST(:emb AS vector)) as score
            FROM vec_chunk_index
            {where_clause}
            ORDER BY embedding <=> CAST(:emb AS vector)
            LIMIT :k
        """),
        params,
    )

    results = []
    for row in result.fetchall():
        score = float(row.score)
        if score >= min_score:
            meta = row.metadata if isinstance(row.metadata, dict) else {}
            results.append(SearchResult(
                index_type="chunk",
                score=score,
                chunk_text=row.chunk_text,
                source_file=row.source_file,
                connector_id=row.connector_id,
                metadata=meta,
            ))
    return results


async def get_table_schema_from_metadata(db: AsyncSession, table_names: list[str]) -> str:
    """Build a schema description string from column_metadata for the given tables."""
    if not table_names:
        return ""

    placeholders = ", ".join([f":t{i}" for i in range(len(table_names))])
    params = {f"t{i}": t for i, t in enumerate(table_names)}

    result = await db.execute(
        text(f"""
            SELECT table_name, column_name, data_type, description
            FROM column_metadata
            WHERE table_name IN ({placeholders})
            ORDER BY table_name, column_name
        """),
        params,
    )

    schema_lines = []
    current_table = None
    for row in result.fetchall():
        if row.table_name != current_table:
            current_table = row.table_name
            schema_lines.append(f"\nTable: {current_table}")
        desc = f" — {row.description}" if row.description else ""
        schema_lines.append(f"  - {row.column_name} ({row.data_type}){desc}")

    return "\n".join(schema_lines)
