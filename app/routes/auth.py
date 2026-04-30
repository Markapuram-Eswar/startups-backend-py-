"""Auth endpoints — parity with backend/src/controllers/authController.js + routes/authRoutes.js."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import TokenUser, admin_only, protect
from app.mail_out import send_email_with_template
from app.models import Role, User
from app.util_ids import new_cuid

router = APIRouter(prefix="/api/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

OTP_TTL_MS = 10 * 60 * 1000
RESET_OTP_TTL_MS = 15 * 60 * 1000


def _jwt_secret() -> str:
    return settings.jwt_secret or "dev-only-change-me"


def sign_token(user: User) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=1)
    payload: dict[str, Any] = {"id": user.id, "role": user.role.value, "exp": exp}
    return jwt.encode(payload, _jwt_secret(), algorithm="HS256")


def generate_otp() -> str:
    return str(secrets.randbelow(900000) + 100000)


@router.post("/login")
async def login(body: dict, db: Session = Depends(get_db)):
    email = body.get("email")
    password = body.get("password")
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail={"message": "User not found"})
    if not user.password or not pwd_context.verify(password, user.password):
        raise HTTPException(status_code=400, detail={"message": "Invalid password"})
    token = sign_token(user)
    out = {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "password": user.password,
        "role": user.role.value,
        "loginOtpHash": user.login_otp_hash,
        "loginOtpExpiresAt": user.login_otp_expires_at,
        "resetOtpHash": user.reset_otp_hash,
        "resetOtpExpiresAt": user.reset_otp_expires_at,
        "createdByAdminId": user.created_by_admin_id,
        "createdByAdminName": user.created_by_admin_name,
        "welcomeEmailSent": user.welcome_email_sent,
        "forcePasswordReset": user.force_password_reset,
        "createdAt": user.created_at,
        "updatedAt": user.updated_at,
    }
    return {"token": token, "user": {**out, "_id": user.id}}


@router.post("/login/request-otp")
async def request_login_otp(body: dict, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    email = body.get("email")
    password = body.get("password")
    if not email or not password:
        raise HTTPException(status_code=400, detail={"message": "Email & password required"})
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail={"message": "User not found"})
    if not user.password or not pwd_context.verify(password, user.password):
        raise HTTPException(status_code=400, detail={"message": "Invalid credentials"})
    otp = generate_otp()
    if settings.show_otp_in_response:
        print(f"[DEV OTP] login {email}: {otp}")
    user.login_otp_hash = pwd_context.hash(otp)
    user.login_otp_expires_at = datetime.utcnow() + timedelta(milliseconds=OTP_TTL_MS)
    db.add(user)
    db.commit()
    background_tasks.add_task(send_email_with_template, user.email, "login_otp", {"otp": otp})
    return {"message": "OTP sent to your email", "otpRequired": True}


@router.post("/login/verify-otp")
async def verify_login_otp(body: dict, db: Session = Depends(get_db)):
    email = body.get("email")
    otp = body.get("otp")
    if not email or not otp:
        raise HTTPException(status_code=400, detail={"message": "Email & OTP required"})
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail={"message": "User not found"})
    if (
        not user.login_otp_hash
        or not user.login_otp_expires_at
        or user.login_otp_expires_at < datetime.utcnow()
    ):
        raise HTTPException(status_code=400, detail={"message": "OTP expired"})
    if not pwd_context.verify(str(otp), user.login_otp_hash):
        raise HTTPException(status_code=400, detail={"message": "Invalid OTP"})
    user.login_otp_hash = None
    user.login_otp_expires_at = None
    db.add(user)
    db.commit()
    token = sign_token(user)
    return {
        "message": "Login successful",
        "token": token,
        "user": {
            "_id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role.value,
            "forcePasswordReset": user.force_password_reset or False,
        },
    }


@router.post("/forgot-password/request-otp")
async def request_password_reset_otp(body: dict, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    email = body.get("email")
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail={"message": "User not found"})
    otp = generate_otp()
    if settings.show_otp_in_response:
        print(f"[DEV OTP] reset {email}: {otp}")
    user.reset_otp_hash = pwd_context.hash(otp)
    user.reset_otp_expires_at = datetime.utcnow() + timedelta(milliseconds=RESET_OTP_TTL_MS)
    db.add(user)
    db.commit()
    background_tasks.add_task(send_email_with_template, user.email, "reset_otp", {"otp": otp})
    return {"message": "Reset OTP sent"}


@router.post("/forgot-password/reset")
async def reset_password(body: dict, db: Session = Depends(get_db)):
    email = body.get("email")
    otp = body.get("otp")
    new_password = body.get("newPassword")
    if not new_password or len(new_password) < 6:
        raise HTTPException(status_code=400, detail={"message": "Password must be at least 6 characters"})
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail={"message": "User not found"})
    if (
        not user.reset_otp_hash
        or not user.reset_otp_expires_at
        or user.reset_otp_expires_at < datetime.utcnow()
    ):
        raise HTTPException(status_code=400, detail={"message": "OTP expired"})
    if not pwd_context.verify(str(otp), user.reset_otp_hash):
        raise HTTPException(status_code=400, detail={"message": "Invalid OTP"})
    user.password = pwd_context.hash(new_password)
    user.reset_otp_hash = None
    user.reset_otp_expires_at = None
    db.add(user)
    db.commit()
    return {"message": "Password reset successful"}


@router.post("/force-reset-password/request-otp")
async def request_force_reset_otp(background_tasks: BackgroundTasks, user: TokenUser = Depends(protect), db: Session = Depends(get_db)):
    row = db.execute(select(User).where(User.id == user.id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail={"message": "User not found"})
    otp = generate_otp()
    if settings.show_otp_in_response:
        print(f"[DEV OTP] force-reset {row.email}: {otp}")
    row.reset_otp_hash = pwd_context.hash(otp)
    row.reset_otp_expires_at = datetime.utcnow() + timedelta(milliseconds=RESET_OTP_TTL_MS)
    db.add(row)
    db.commit()
    background_tasks.add_task(send_email_with_template, row.email, "reset_otp", {"otp": otp})
    return {"message": "Verification code sent to your email"}


@router.post("/force-reset-password")
async def force_password_reset(body: dict, user: TokenUser = Depends(protect), db: Session = Depends(get_db)):
    new_password = body.get("newPassword")
    otp = body.get("otp")
    if not otp:
        raise HTTPException(status_code=400, detail={"message": "Verification code is required"})
    if not new_password or len(new_password) < 6:
        raise HTTPException(status_code=400, detail={"message": "Password must be at least 6 characters"})
    row = db.execute(select(User).where(User.id == user.id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail={"message": "User not found"})
    if (
        not row.reset_otp_hash
        or not row.reset_otp_expires_at
        or row.reset_otp_expires_at < datetime.utcnow()
    ):
        raise HTTPException(status_code=400, detail={"message": "Verification code expired"})
    if not pwd_context.verify(str(otp), row.reset_otp_hash):
        raise HTTPException(status_code=400, detail={"message": "Invalid verification code"})
    row.password = pwd_context.hash(new_password)
    row.force_password_reset = False
    row.reset_otp_hash = None
    row.reset_otp_expires_at = None
    db.add(row)
    db.commit()
    return {
        "message": "Password reset successfully",
        "user": {
            "_id": row.id,
            "name": row.name,
            "email": row.email,
            "role": row.role.value,
            "forcePasswordReset": False,
        },
    }


@router.post("/admin/create-user")
async def admin_create_user(
    body: dict,
    background_tasks: BackgroundTasks,
    admin: TokenUser = Depends(admin_only),
    db: Session = Depends(get_db),
):
    email = body.get("email")
    password = body.get("password")
    name = body.get("name")
    send_welcome = body.get("sendWelcome")
    force_password_reset = body.get("forcePasswordReset") or False
    if not email or not password:
        raise HTTPException(
            status_code=400,
            detail={"message": "Email and password are required"},
        )
    if len(password) < 6:
        raise HTTPException(status_code=400, detail={"message": "Password must be at least 6 characters"})
    exists = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail={"message": "User with this email already exists"})
    admin_row = db.execute(select(User).where(User.id == admin.id)).scalar_one_or_none()
    admin_name = (admin_row.name if admin_row else None) or "Admin"
    now = datetime.utcnow()
    new_user = User(
        id=new_cuid(),
        name=name.strip() if name else None,
        email=email.strip(),
        password=pwd_context.hash(password),
        role=Role.user,
        created_by_admin_id=admin.id,
        created_by_admin_name=admin_name,
        welcome_email_sent=False,
        force_password_reset=bool(force_password_reset),
        created_at=now,
        updated_at=now,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    if send_welcome:
        email_data = {
            "name": new_user.name,
            "email": new_user.email,
            "password": password,
            "loginUrl": settings.frontend_url,
        }
        background_tasks.add_task(send_email_with_template, new_user.email, "welcome_invitation", email_data)
        new_user.welcome_email_sent = True
        db.add(new_user)
        db.commit()
    return {
        "message": "User created successfully",
        "user": {
            "_id": new_user.id,
            "name": new_user.name,
            "email": new_user.email,
            "role": new_user.role.value,
            "createdByAdminName": new_user.created_by_admin_name,
            "createdAt": new_user.created_at,
            "welcomeEmailSent": new_user.welcome_email_sent,
            "forcePasswordReset": new_user.force_password_reset,
        },
    }


@router.get("/admin/user-creation-history")
async def get_user_creation_history(admin: TokenUser = Depends(admin_only), db: Session = Depends(get_db)):
    rows = (
        db.execute(
            select(User)
            .where(User.created_by_admin_id.is_not(None))
            .order_by(User.created_at.desc())
            .limit(10)
        )
        .scalars()
        .all()
    )
    result = []
    for u in rows:
        result.append(
            {
                "id": u.id,
                "name": u.name,
                "email": u.email,
                "createdByAdminName": u.created_by_admin_name,
                "createdAt": u.created_at,
                "welcomeEmailSent": u.welcome_email_sent,
                "_id": u.id,
            }
        )
    return result
