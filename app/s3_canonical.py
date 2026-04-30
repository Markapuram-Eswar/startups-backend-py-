"""Stable S3 URLs — strip SigV4 presign query params (canonicalS3Url.js)."""

from __future__ import annotations


def strip_aws_presigned_query(stored: str | None) -> str:
    s = str(stored or "").strip()
    if not s or "X-Amz-" not in s:
        return s
    try:
        from urllib.parse import urlparse, urlunparse

        u = urlparse(s)
        if "amazonaws.com" not in (u.hostname or ""):
            return s
        return urlunparse((u.scheme, u.netloc, u.path, "", "", ""))
    except Exception:
        return s
