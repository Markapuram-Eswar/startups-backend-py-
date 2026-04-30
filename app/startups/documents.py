"""Document list normalization — mirrors startupController normalizeDocuments."""

from __future__ import annotations

from typing import Any

from app.s3_canonical import strip_aws_presigned_query
from app.trusted_upload import is_trusted_document_url

MAX_STARTUP_DOCUMENTS = 10


def normalize_documents(docs: Any) -> list[dict]:
    if not isinstance(docs, list):
        return []
    out: list[dict] = []
    for d in docs:
        if not d or not isinstance(d, dict):
            continue
        url_raw = d.get("url")
        if not isinstance(url_raw, str):
            continue
        stripped = strip_aws_presigned_query(url_raw.strip())
        if not is_trusted_document_url(stripped):
            continue
        item: dict[str, Any] = {
            "url": stripped,
            "fileName": str(d.get("fileName") or "document")[:200],
        }
        if d.get("contentType"):
            item["contentType"] = str(d.get("contentType"))[:120]
        out.append(item)
    return out[:MAX_STARTUP_DOCUMENTS]
