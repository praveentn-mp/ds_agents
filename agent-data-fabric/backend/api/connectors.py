"""Connectors API — CRUD, test, schema discovery."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.connector import (
    ConnectorCreate, ConnectorUpdate, ConnectorResponse, ConnectorTestResult, SchemaDiscoveryResult,
)
from backend.services.connector_service import (
    list_connectors, get_connector, create_connector, update_connector, delete_connector,
    test_connector, discover_schema,
)
from backend.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/connectors", tags=["connectors"])


@router.get("", response_model=list[ConnectorResponse])
async def list_all(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    connectors = await list_connectors(db)
    return connectors


@router.post("", response_model=ConnectorResponse, status_code=201)
async def create(
    data: ConnectorCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    connector = await create_connector(db, data.model_dump(), owner_id=user.id)
    return connector


@router.get("/{connector_id}", response_model=ConnectorResponse)
async def get_one(connector_id: UUID, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    connector = await get_connector(db, connector_id)
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    return connector


@router.put("/{connector_id}", response_model=ConnectorResponse)
async def update(
    connector_id: UUID,
    data: ConnectorUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    connector = await update_connector(db, connector_id, data.model_dump(exclude_unset=True))
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    return connector


@router.delete("/{connector_id}")
async def delete(connector_id: UUID, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    deleted = await delete_connector(db, connector_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Connector not found")
    return {"message": "Deleted"}


@router.post("/{connector_id}/test", response_model=ConnectorTestResult)
async def test(connector_id: UUID, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    result = await test_connector(db, connector_id)
    return result


@router.post("/{connector_id}/discover-schema")
async def schema(connector_id: UUID, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    try:
        result = await discover_schema(db, connector_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
