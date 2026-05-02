"""Resolve logo/document URLs + presign — mirrors backend/src/utils/resolvePublicAssetUrl.js."""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.s3_ops import is_s3_configured, public_url_for_key
from app.s3_presign import presign_reads_enabled, presigned_get_url_for_stored


def resolve_public_asset_url(stored: str | None) -> str:
    s = str(stored or "").strip()
    if not s:
        return ""
    if s.lower().startswith(("http://", "https://")):
        return s
    if s.startswith("//"):
        return f"https:{s}"
    key = s.lstrip("/")
    if key.startswith("uploads/") and is_s3_configured():
        return public_url_for_key(key)
    return s


def serialize_documents_sync(documents: Any) -> Any:
    if documents is None:
        return documents
    if not isinstance(documents, list):
        return documents
    out = []
    for d in documents:
        if not d or not isinstance(d, dict):
            out.append(d)
            continue
        item = dict(d)
        if isinstance(item.get("url"), str):
            item["url"] = resolve_public_asset_url(item["url"].strip())
        out.append(item)
    return out


def serialize_startup_for_client_sync(row_dict: dict) -> dict:
    s = dict(row_dict)
    if isinstance(s.get("logo"), str) and s["logo"].strip():
        resolved = resolve_public_asset_url(s["logo"].strip())
        s["logo"] = resolved or None
    if s.get("documents") is not None:
        s["documents"] = serialize_documents_sync(s["documents"])
    return s


async def serialize_startup_for_client_async(row_dict: dict, opts: dict | None = None) -> dict:
    opts = opts or {}
    if bool(opts.get("lightList")):
        # No S3 presign (avoids boto3 credential/IMDS delays on local dev after login)
        return serialize_startup_for_client_sync(row_dict)
    if not presign_reads_enabled():
        return serialize_startup_for_client_sync(row_dict)

    s = dict(row_dict)
    sid = s.get("id")

    if isinstance(s.get("logo"), str) and s["logo"].strip():
        raw = s["logo"].strip()
        signed = presigned_get_url_for_stored(raw)
        if signed:
            s["logo"] = signed
        else:
            resolved = resolve_public_asset_url(raw)
            key_like = raw.lstrip("/")
            # Only use media streaming if S3 is configured with keys (avoids 503/500 if missing)
            has_keys = bool(settings.aws_access_key_id and settings.aws_secret_access_key)
            looks_private = ("amazonaws.com" in raw.lower()) or key_like.startswith("uploads/")
            
            if looks_private and sid and has_keys:
                s["logo"] = f"/api/media/startup/{sid}/logo"
            else:
                s["logo"] = resolved or None

    docs = s.get("documents")
    if docs is not None and isinstance(docs, list):
        new_docs = []
        for i, d in enumerate(docs):
            if not d or not isinstance(d, dict):
                new_docs.append(d)
                continue
            item = dict(d)
            if isinstance(item.get("url"), str):
                raw_u = item["url"].strip()
                signed_u = presigned_get_url_for_stored(raw_u)
                if signed_u:
                    item["url"] = signed_u
                else:
                    resolved_u = resolve_public_asset_url(raw_u)
                    # Only use media streaming if S3 is configured with keys
                    has_keys = bool(settings.aws_access_key_id and settings.aws_secret_access_key)
                    kl = raw_u.lstrip("/")
                    lp = ("amazonaws.com" in raw_u.lower()) or kl.startswith("uploads/")
                    item["url"] = (
                        f"/api/media/startup/{sid}/document/{i}"
                        if lp and sid and has_keys
                        else resolved_u
                    )
            new_docs.append(item)
        s["documents"] = new_docs

    return s
