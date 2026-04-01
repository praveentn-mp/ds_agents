"""Auth API — login, refresh, logout."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.auth import LoginRequest, TokenResponse, RefreshRequest, UserResponse, UserCreate
from backend.services.auth_service import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_token,
    create_user,
    get_user_by_id,
)
from backend.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, req.email, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(req.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = payload.get("sub")
    access_token = create_access_token({"sub": user_id})
    refresh_token = create_refresh_token({"sub": user_id})
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.delete("/logout")
async def logout(user=Depends(get_current_user)):
    return {"message": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def me(user=Depends(get_current_user)):
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role_name=user.role.name if user.role else None,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post("/register", response_model=UserResponse)
async def register(req: UserCreate, db: AsyncSession = Depends(get_db)):
    user = await create_user(db, req.email, req.password, req.full_name, req.role_name)
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role_name=req.role_name,
        is_active=user.is_active,
        created_at=user.created_at,
    )
