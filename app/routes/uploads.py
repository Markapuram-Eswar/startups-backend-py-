"""Upload + presigned image URL — parity with uploadRoutes + uploadController + get-image-url."""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import JSONResponse

from app.config import settings
from app.deps import protect
from app.deps import TokenUser
from app.s3_ops import is_s3_configured, put_object_bytes
from app.s3_presign import presigned_get_url_for_stored
from app.asset_resolve import resolve_public_asset_url
from app.s3_presign import presign_reads_enabled

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

MIME_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "application/pdf": ".pdf",
}
ALLOWED = set(MIME_EXT)


@router.get("/health")
async def uploads_health() -> JSONResponse:
    return JSONResponse({"ok": True, "uploads": True})


@router.get("/get-image-url")
async def get_image_url(
    user: TokenUser = Depends(protect),
    path: str = Query(..., description="S3 key or trusted URL"),
):
    if not path.strip():
        return JSONResponse({"status": "false", "message": "Missing query parameter: path"}, status_code=400)
    signed = presigned_get_url_for_stored(path)
    if signed:
        return {"status": "true", "url": signed, "source": "presigned"}
    resolved = resolve_public_asset_url(path)
    if resolved:
        return {
            "status": "true",
            "url": resolved,
            "source": "resolved-fallback" if presign_reads_enabled() else "public",
        }
    return JSONResponse({"status": "false", "message": "Invalid or untrusted path"}, status_code=400)


@router.post("/startup-asset")
async def upload_startup_asset(
    user: TokenUser = Depends(protect),
    file: UploadFile = File(...),
    kind: str | None = None,
):
    if not is_s3_configured():
        return JSONResponse(
            {
                "message": "File storage is not configured. Set S3_BUCKET_NAME and AWS credentials on the server.",
            },
            status_code=503,
        )
    data = await file.read()
    if not data:
        return JSONResponse({"message": "Missing file (use multipart field name: file)"}, status_code=400)
    ct = file.content_type or "application/octet-stream"
    if ct not in ALLOWED:
        return JSONResponse(
            {"message": "Unsupported file type. Allowed: JPEG, PNG, WebP, GIF, PDF."},
            status_code=400,
        )
    if len(data) > 20 * 1024 * 1024:
        return JSONResponse({"message": "File too large (maximum 20 MB)."}, status_code=400)

    ext = MIME_EXT.get(ct) or Path(file.filename or "file").suffix[:8] or ".bin"
    user_id = user.id or "anonymous"
    stamp = f"{int(__import__('time').time() * 1000)}-{uuid.uuid4()}"
    base = re.sub(r"[^\w.-]+", "_", Path(file.filename or "file").stem)[:60]
    key = f"uploads/{user_id}/{stamp}-{base}{ext}"

    canonical_url = put_object_bytes(buffer=data, content_type=ct, key=key)
    url = canonical_url
    presigned = presigned_get_url_for_stored(canonical_url) or presigned_get_url_for_stored(key)
    if presigned:
        url = presigned

    return {
        "url": url,
        "canonicalUrl": canonical_url,
        "key": key,
        "fileName": file.filename or f"file{ext}",
        "contentType": ct,
    }
