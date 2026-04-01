"""Authentication service — JWT + password hashing."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import bcrypt
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.user import User
from backend.models.role import Role


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email, User.is_active == True))
    user = result.scalar_one_or_none()
    if user and verify_password(password, user.hashed_password):
        user.last_login = datetime.now(timezone.utc)
        await db.flush()
        return user
    return None


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> Optional[User]:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, email: str, password: str, full_name: str, role_name: str = "viewer") -> User:
    role_result = await db.execute(select(Role).where(Role.name == role_name))
    role = role_result.scalar_one_or_none()

    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        role_id=role.id if role else None,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user
