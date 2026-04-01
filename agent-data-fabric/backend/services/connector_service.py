"""Connector service — CRUD, test, schema discovery."""

import time
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.connector import Connector
from backend.models.connector_schema import ConnectorSchema
from backend.models.mcp_resource import MCPResource
from backend.connectors.base import BaseConnector
from backend.connectors.registry import connector_registry
from backend.connectors.credentials import encrypt_credentials, decrypt_credentials
from backend.connectors.postgres_connector import PostgresConnector
from backend.connectors.azure_blob_connector import AzureBlobConnector
from backend.connectors.filesystem_connector import FilesystemConnector

CONNECTOR_CLASSES = {
    "postgres": PostgresConnector,
    "azure_blob": AzureBlobConnector,
    "filesystem": FilesystemConnector,
}


def _build_connector(record: Connector) -> BaseConnector:
    cls = CONNECTOR_CLASSES.get(record.connector_type)
    if not cls:
        raise ValueError(f"Unknown connector type: {record.connector_type}")
    creds = {}
    if record.encrypted_credentials:
        creds = decrypt_credentials(record.encrypted_credentials)
    return cls(name=record.name, config=record.config or {}, credentials=creds)


async def list_connectors(db: AsyncSession) -> list[Connector]:
    result = await db.execute(select(Connector).order_by(Connector.created_at.desc()))
    return list(result.scalars().all())


async def get_connector(db: AsyncSession, connector_id: UUID) -> Optional[Connector]:
    result = await db.execute(select(Connector).where(Connector.id == connector_id))
    return result.scalar_one_or_none()


async def create_connector(db: AsyncSession, data: dict, owner_id: Optional[UUID] = None) -> Connector:
    encrypted_creds = None
    if data.get("credentials"):
        encrypted_creds = encrypt_credentials(data["credentials"])

    connector = Connector(
        name=data["name"],
        connector_type=data["connector_type"],
        description=data.get("description"),
        config=data.get("config", {}),
        encrypted_credentials=encrypted_creds,
        sync_mode=data.get("sync_mode", "live"),
        sync_interval_seconds=data.get("sync_interval_seconds", 3600),
        owner_id=owner_id,
    )
    db.add(connector)
    await db.flush()
    await db.refresh(connector)

    # Register in connector registry
    try:
        instance = _build_connector(connector)
        connector_registry.register(connector.name, instance)
    except Exception:
        pass

    # Register MCP resources
    await _register_connector_resources(db, connector)
    return connector


async def _register_connector_resources(db: AsyncSession, connector: Connector):
    """Auto-register MCP resources for a connector."""
    uri = f"connector://{connector.connector_type}/{connector.name}"
    existing = await db.execute(select(MCPResource).where(MCPResource.uri == uri))
    if existing.scalar_one_or_none() is None:
        resource = MCPResource(
            uri=uri,
            name=connector.name,
            description=connector.description or f"{connector.connector_type} connector",
            resource_type="data_resource",
            source_type="connector",
            source_id=connector.id,
            mime_type="application/json",
        )
        db.add(resource)
        await db.flush()


async def update_connector(db: AsyncSession, connector_id: UUID, data: dict) -> Optional[Connector]:
    result = await db.execute(select(Connector).where(Connector.id == connector_id))
    connector = result.scalar_one_or_none()
    if not connector:
        return None

    if data.get("name") is not None:
        connector.name = data["name"]
    if data.get("description") is not None:
        connector.description = data["description"]
    if data.get("config") is not None:
        connector.config = data["config"]
    if data.get("credentials"):
        connector.encrypted_credentials = encrypt_credentials(data["credentials"])
    if data.get("sync_mode") is not None:
        connector.sync_mode = data["sync_mode"]
    if data.get("sync_interval_seconds") is not None:
        connector.sync_interval_seconds = data["sync_interval_seconds"]
    if data.get("is_active") is not None:
        connector.is_active = data["is_active"]

    await db.flush()
    await db.refresh(connector)

    # Re-register in registry
    try:
        connector_registry.unregister(connector.name)
        instance = _build_connector(connector)
        connector_registry.register(connector.name, instance)
    except Exception:
        pass

    return connector


async def delete_connector(db: AsyncSession, connector_id: UUID) -> bool:
    result = await db.execute(select(Connector).where(Connector.id == connector_id))
    connector = result.scalar_one_or_none()
    if not connector:
        return False
    connector_registry.unregister(connector.name)
    await db.delete(connector)
    await db.flush()
    return True


async def test_connector(db: AsyncSession, connector_id: UUID) -> dict:
    result = await db.execute(select(Connector).where(Connector.id == connector_id))
    connector = result.scalar_one_or_none()
    if not connector:
        return {"success": False, "latency_ms": 0, "message": "Connector not found"}
    try:
        instance = _build_connector(connector)
        result = await instance.test_connection()
        await instance.close()
        # Auto-activate connector on successful test
        if result.get("success") and not connector.is_active:
            connector.is_active = True
            await db.flush()
        return result
    except Exception as e:
        return {"success": False, "latency_ms": 0, "message": str(e)}


async def discover_schema(db: AsyncSession, connector_id: UUID) -> dict:
    result = await db.execute(select(Connector).where(Connector.id == connector_id))
    connector = result.scalar_one_or_none()
    if not connector:
        raise ValueError("Connector not found")

    instance = _build_connector(connector)
    schema = await instance.discover_schema()
    await instance.close()

    # Save schema version
    latest = await db.execute(
        select(ConnectorSchema)
        .where(ConnectorSchema.connector_id == connector_id, ConnectorSchema.is_current == True)
    )
    existing = latest.scalar_one_or_none()
    new_version = (existing.version + 1) if existing else 1

    if existing:
        existing.is_current = False

    cs = ConnectorSchema(
        connector_id=connector_id,
        version=new_version,
        schema_json=schema,
        is_current=True,
    )
    db.add(cs)
    await db.flush()

    return {
        "connector_id": str(connector_id),
        "version": new_version,
        "schema_json": schema,
        "discovered_at": str(cs.discovered_at),
    }
