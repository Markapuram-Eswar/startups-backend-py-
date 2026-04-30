"""Trust rules for document URLs (trustedUploadUrl.js)."""

from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

from app.config import settings


def is_trusted_document_url(raw: str | None) -> bool:
    trimmed = str(raw or "").strip()
    if not trimmed:
        return False
    try:
        u = urlparse(trimmed)
    except Exception:
        return False

    is_local_http = u.scheme == "http" and u.hostname in ("localhost", "127.0.0.1")
    if u.scheme != "https" and not is_local_http:
        return False

    bucket = (settings.s3_bucket_name or "").strip()
    if not bucket:
        return True

    pub = (settings.s3_public_base_url or "").strip().rstrip("/")
    if pub:
        t = trimmed.lower()
        p = pub.lower()
        if t == p or t.startswith(f"{p}/"):
            return True

    host = (u.hostname or "").lower()
    bucket_lower = bucket.lower()
    pathname = (u.path or "").lstrip("/")
    try:
        norm_path = unquote(pathname).lower()
    except Exception:
        norm_path = pathname.lower()

    if host == f"{bucket_lower}.s3.amazonaws.com":
        return norm_path.startswith("uploads/")

    if host == f"{bucket_lower}.s3-accelerate.amazonaws.com":
        return norm_path.startswith("uploads/")

    if (
        host.startswith(f"{bucket_lower}.s3.") or host.startswith(f"{bucket_lower}.s3-")
    ) and (host.endswith(".amazonaws.com") or host.endswith(".amazonaws.com.cn")):
        return norm_path.startswith("uploads/")

    path_style = host == "s3.amazonaws.com" or bool(
        re.match(r"^s3(?:\.dualstack)?\.[a-z0-9-]+\.amazonaws\.com(\.cn)?$", host)
    )
    if path_style:
        prefix = f"{bucket_lower}/uploads/"
        return norm_path.startswith(prefix)

    return False
