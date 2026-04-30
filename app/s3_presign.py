"""Presigned GET URLs — mirrors backend/src/config/s3Presign.js."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from app.config import settings
from app.s3_ops import get_bucket_region, get_s3_client, is_s3_configured
from app.trusted_upload import is_trusted_document_url

logger = logging.getLogger(__name__)

MAX_EXPIRY = 604800


def get_presign_expiry_seconds() -> int:
    if not (settings.s3_bucket_name or "").strip():
        return 0
    raw = settings.s3_presigned_get_seconds
    if raw is None or str(raw).strip() == "":
        return 3600
    try:
        n = int(str(raw).strip(), 10)
    except ValueError:
        return 3600
    if n <= 0:
        return 0
    return min(n, MAX_EXPIRY)


def presign_reads_enabled() -> bool:
    return get_presign_expiry_seconds() > 0


def extract_uploads_object_key(stored: str | None) -> str | None:
    s = str(stored or "").strip()
    if not s:
        return None
    bare = s.split("?")[0].lstrip("/")
    if bare.startswith("uploads/"):
        return bare

    if not s.lower().startswith(("http://", "https://")):
        return None
    if not is_trusted_document_url(s):
        return None

    try:
        u = urlparse(s.strip())
        path = (u.path or "").lstrip("/").split("?")[0]
        bucket = (settings.s3_bucket_name or "").strip()
        prefix = f"{bucket}/".lower()
        lp = path.lower()
        if lp.startswith(prefix):
            path = path[len(bucket) + 1 :]
        return path if path.startswith("uploads/") else None
    except Exception:
        return None


def presigned_get_url_for_stored(stored: str | None) -> str | None:
    key = extract_uploads_object_key(stored)
    if not key:
        if presign_reads_enabled() and "amazonaws.com" in str(stored or ""):
            logger.warning(
                "[s3Presign] Cannot presign (untrusted URL or bad path). First 120 chars: %s",
                str(stored)[:120],
            )
        return None

    bucket = (settings.s3_bucket_name or "").strip()
    if not bucket:
        return None

    expires_in = get_presign_expiry_seconds()
    if not expires_in:
        return None

    try:
        client = get_s3_client()
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )
    except Exception as e:
        logger.error("[s3Presign] presigned GET failed: %s %s", key, e)
        return None
