"""PostgreSQL connector — live querying + schema discovery."""

import time
import asyncpg
from typing import Optional
from backend.connectors.base import BaseConnector


class PostgresConnector(BaseConnector):
    def __init__(self, name: str, config: dict, credentials: Optional[dict] = None):
        super().__init__(name, config, credentials)
        self._pool: Optional[asyncpg.Pool] = None

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            host = self.credentials.get("host") or self.config.get("host", "localhost")
            port = int(self.credentials.get("port") or self.config.get("port", 5432))
            database = self.credentials.get("database") or self.config.get("database", "postgres")
            user = self.credentials.get("user") or self.config.get("user", "postgres")
            password = self.credentials.get("password") or self.config.get("password", "")
            self._pool = await asyncpg.create_pool(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
                min_size=2,
                max_size=10,
            )
        return self._pool

    async def test_connection(self) -> dict:
        start = time.monotonic()
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            latency = int((time.monotonic() - start) * 1000)
            return {"success": True, "latency_ms": latency, "message": "Connection successful"}
        except Exception as e:
            latency = int((time.monotonic() - start) * 1000)
            return {"success": False, "latency_ms": latency, "message": str(e)}

    async def discover_schema(self) -> dict:
        pool = await self._get_pool()
        schema = {"tables": []}
        async with pool.acquire() as conn:
            tables = await conn.fetch("""
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY table_schema, table_name
            """)
            for table in tables:
                columns = await conn.fetch("""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema = $1 AND table_name = $2
                    ORDER BY ordinal_position
                """, table["table_schema"], table["table_name"])
                schema["tables"].append({
                    "schema": table["table_schema"],
                    "name": table["table_name"],
                    "columns": [
                        {
                            "name": col["column_name"],
                            "type": col["data_type"],
                            "nullable": col["is_nullable"] == "YES",
                            "default": col["column_default"],
                        }
                        for col in columns
                    ],
                })
        return schema

    async def execute_query(self, query: str, params: Optional[dict] = None) -> list[dict]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(query)
            return [dict(row) for row in rows]

    async def write(self, resource: str, payload: dict) -> dict:
        pool = await self._get_pool()
        columns = ", ".join(payload.keys())
        placeholders = ", ".join(f"${i+1}" for i in range(len(payload)))
        query = f"INSERT INTO {resource} ({columns}) VALUES ({placeholders}) RETURNING *"
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, *payload.values())
            return dict(row) if row else {}

    async def close(self):
        if self._pool:
            await self._pool.close()
            self._pool = None
