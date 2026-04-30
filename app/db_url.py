"""Build PostgreSQL URL and SSL options — mirrors backend/src/config/databaseUrl.js."""

from __future__ import annotations

from urllib.parse import parse_qsl, quote_plus, urlencode, urlparse, urlunparse

from app.config import settings


def _relaxed_ssl() -> bool:
    v = str(settings.db_ssl_reject_unauthorized).lower()
    return v in ("false", "0", "no")


def _with_sslmode_require(direct: str) -> str:
    """Force sslmode=require (TLS without cert verification; works with libpq / Psycopg 3)."""
    u = urlparse(direct)
    q = dict(parse_qsl(u.query, keep_blank_values=True))
    q["sslmode"] = "require"
    new_query = urlencode(q)
    # SQLAlchemy: use the Psycopg 3 driver
    scheme = u.scheme
    if scheme in ("postgresql", "postgres"):
        scheme = "postgresql+psycopg"
    return urlunparse((scheme, u.netloc, u.path, u.params, new_query, u.fragment))


def get_database_url() -> str:
    direct = (settings.database_url or "").strip()
    if direct:
        if _relaxed_ssl():
            try:
                return _with_sslmode_require(direct)
            except Exception:
                return direct
        return direct

    host = (settings.db_host or "").strip()
    user = (settings.db_user or "").strip()
    db_name = (settings.db_name or "").strip()
    if not host or not user or not db_name:
        raise RuntimeError(
            "Database URL missing: set DATABASE_URL or DB_HOST, DB_USER, and DB_NAME in .env"
        )

    port = str(settings.db_port or "5432").strip()
    password = settings.db_password or ""
    sslmode = str(settings.db_sslmode or "require").strip().lower()

    user_enc = quote_plus(user)
    pass_enc = quote_plus(password)

    if _relaxed_ssl():
        return f"postgresql+psycopg://{user_enc}:{pass_enc}@{host}:{port}/{quote_plus(db_name)}?sslmode=require"

    query = ""
    if sslmode and sslmode not in ("disable", "false"):
        query = f"?sslmode={quote_plus(sslmode)}"
    return f"postgresql+psycopg://{user_enc}:{pass_enc}@{host}:{port}/{quote_plus(db_name)}{query}"


def get_connect_args() -> dict:
    """Psycopg 3 uses libpq conninfo only — TLS is configured via sslmode in the URL, not connect_args."""
    return {}
