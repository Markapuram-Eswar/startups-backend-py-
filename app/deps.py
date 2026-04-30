"""JWT + admin-key auth — mirrors backend/src/middleware/authMiddleware.js and startupRoutes checkAdmin."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Optional

import jwt
from fastapi import Depends, Header, HTTPException, Request
from jwt import ExpiredSignatureError, InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Role, User


@dataclass
class TokenUser:
    id: str
    role: str
    email: Optional[str] = None
    name: Optional[str] = None


def _jwt_secret() -> str:
    return settings.jwt_secret or "dev-only-change-me"


def decode_bearer_token(token: str) -> TokenUser:
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=["HS256"])
        uid = payload.get("id")
        role = payload.get("role")
        if not uid or not role:
            raise HTTPException(status_code=401, detail={"message": "Invalid token"})
        return TokenUser(id=str(uid), role=str(role))
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail={"message": "Invalid token"})
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail={"message": "Invalid token"})


def get_token_from_header(authorization: Optional[str]) -> Optional[str]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return authorization[7:].strip() or None


async def protect(
    request: Request,
    db: Session = Depends(get_db),
    authorization: Annotated[Optional[str], Header()] = None,
) -> TokenUser:
    # Also read from request if Header() missed
    auth = authorization or request.headers.get("authorization")
    token = get_token_from_header(auth or "")
    if not token:
        raise HTTPException(status_code=401, detail={"message": "No token"})
    u = decode_bearer_token(token)
    row = db.execute(select(User).where(User.id == u.id)).scalar_one_or_none()
    if row:
        u.email = row.email
        u.name = row.name
    return u


async def admin_only(user: TokenUser = Depends(protect)) -> TokenUser:
    if user.role != Role.admin.value and user.role != "admin":
        raise HTTPException(status_code=403, detail={"message": "Admin only"})
    return user


async def check_admin(
    request: Request,
    db: Session = Depends(get_db),
    admin_key: Annotated[Optional[str], Header(alias="admin-key")] = None,
    authorization: Annotated[Optional[str], Header()] = None,
) -> TokenUser:
    ak = admin_key or request.headers.get("admin-key")
    if settings.admin_key and ak == settings.admin_key:
        admin_user = db.execute(select(User).where(User.role == Role.admin)).scalars().first()
        if admin_user:
            return TokenUser(
                id=admin_user.id,
                role=Role.admin.value,
                email=admin_user.email,
                name=admin_user.name,
            )

    auth = authorization or request.headers.get("authorization")
    token = get_token_from_header(auth or "")
    if token:
        try:
            payload = jwt.decode(token, _jwt_secret(), algorithms=["HS256"])
            if payload.get("role") == "admin":
                return TokenUser(
                    id=str(payload.get("id")),
                    role="admin",
                )
            raise HTTPException(status_code=403, detail={"message": "Not an admin user"})
        except HTTPException:
            raise
        except Exception:
            pass

    raise HTTPException(status_code=401, detail={"message": "Unauthorized"})
