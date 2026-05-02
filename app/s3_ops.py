"""S3 upload + public URLs — mirrors backend/src/config/s3.js."""

from __future__ import annotations

import boto3
from botocore.config import Config

from app.config import settings


def get_bucket_region() -> str:
    return str(
        settings.s3_bucket_region or settings.aws_region or "ap-south-1"
    ).strip() or "ap-south-1"


def is_s3_configured() -> bool:
    has_bucket = bool((settings.s3_bucket_name or "").strip())
    has_keys = bool((settings.aws_access_key_id or "").strip() and (settings.aws_secret_access_key or "").strip())
    return has_bucket and has_keys


def public_url_for_key(key: str) -> str:
    from urllib.parse import quote

    parts = [p for p in key.replace("\\", "/").split("/") if p != ""]
    enc_path = "/".join(quote(p, safe="") for p in parts)

    base = (settings.s3_public_base_url or "").strip().rstrip("/")
    if base:
        return f"{base}/{enc_path}"
    bucket = settings.s3_bucket_name
    region = get_bucket_region()
    return f"https://{bucket}.s3.{region}.amazonaws.com/{enc_path}"


_s3_client = None

def get_s3_client():
    global _s3_client
    if _s3_client is not None:
        return _s3_client
        
    kwargs = {"region_name": get_bucket_region()}
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id.strip()
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key.strip()
    
    _s3_client = boto3.client(
        "s3",
        config=Config(signature_version="s3v4"),
        **kwargs,
    )
    return _s3_client


def put_object_bytes(*, buffer: bytes, content_type: str, key: str) -> str:
    bucket = (settings.s3_bucket_name or "").strip()
    if not bucket:
        raise RuntimeError("S3_BUCKET_NAME is not set")
    client = get_s3_client()
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=buffer,
        ContentType=content_type or "application/octet-stream",
        CacheControl="public, max-age=31536000, immutable",
    )
    return public_url_for_key(key)
