"""Auth middleware — JWT token extraction and user injection."""

from typing import Optional
from uuid import UUID

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.services.auth_service import decode_token, get_user_by_id

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = await get_user_by_id(db, UUID(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return user


def require_permission(permission: str):
    """FastAPI dependency — check user has specific permission."""
    async def checker(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
        if user.role:
            permissions = user.role.permissions or []
            if permission in permissions:
                return user
        raise HTTPException(status_code=403, detail=f"Permission '{permission}' required")
    return checker
