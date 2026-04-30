"""Stream media from S3 — parity with mediaRoutes + mediaController."""

from __future__ import annotations

from urllib.parse import quote

from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, Response

from app.database import get_db
from app.deps import TokenUser, protect
from app.models import Startup
from app.s3_ops import get_s3_client, is_s3_configured
from app.s3_presign import extract_uploads_object_key
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/media", tags=["media"])


def _can_access(user: TokenUser | None, startup: Startup) -> bool:
    if not startup:
        return False
    if user and getattr(user, "role", None) == "admin":
        return True
    return bool(user and startup.created_by_id == user.id)


def _stream_s3_key(key: str, filename: str | None) -> Response:
    from app.config import settings

    bucket = (settings.s3_bucket_name or "").strip()
    if not bucket:
        raise HTTPException(status_code=503, detail={"message": "S3 not configured"})
    s3 = get_s3_client()
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("NoSuchKey", "404"):
            raise HTTPException(status_code=404, detail={"message": "Not found"})
        raise HTTPException(status_code=500, detail={"message": str(e)})
    data = obj["Body"].read()
    ct = obj.get("ContentType") or "application/octet-stream"
    headers = {"Cache-Control": "private, no-store"}
    if filename:
        headers["Content-Disposition"] = f"inline; filename*=UTF-8''{quote(filename)}"
    return Response(content=data, media_type=ct, headers=headers)


@router.get("/startup/{startup_id}/logo")
async def stream_logo(startup_id: str, user: TokenUser = Depends(protect), db: Session = Depends(get_db)):
    if not is_s3_configured():
        return JSONResponse({"message": "S3 not configured"}, status_code=503)
    startup = db.get(Startup, startup_id)
    if not startup:
        raise HTTPException(status_code=404, detail={"message": "Startup not found"})
    if not _can_access(user, startup):
        raise HTTPException(status_code=403, detail={"message": "Forbidden"})
    key = extract_uploads_object_key(startup.logo or "")
    if not key:
        raise HTTPException(status_code=404, detail={"message": "No logo file"})
    return _stream_s3_key(key, "logo")


@router.get("/startup/{startup_id}/document/{index}")
async def stream_document(
    startup_id: str,
    index: int,
    user: TokenUser = Depends(protect),
    db: Session = Depends(get_db),
):
    if not is_s3_configured():
        return JSONResponse({"message": "S3 not configured"}, status_code=503)
    startup = db.get(Startup, startup_id)
    if not startup:
        raise HTTPException(status_code=404, detail={"message": "Startup not found"})
    if not _can_access(user, startup):
        raise HTTPException(status_code=403, detail={"message": "Forbidden"})
    if index < 0:
        raise HTTPException(status_code=400, detail={"message": "Invalid index"})
    docs = startup.documents
    if not isinstance(docs, list) or index >= len(docs):
        raise HTTPException(status_code=404, detail={"message": "Document not found"})
    doc = docs[index]
    url = doc.get("url") if isinstance(doc, dict) else None
    key = extract_uploads_object_key(url or "")
    if not key:
        raise HTTPException(status_code=400, detail={"message": "Invalid document URL"})
    fname = doc.get("fileName") if isinstance(doc, dict) else None
    return _stream_s3_key(key, fname or "document.pdf")
