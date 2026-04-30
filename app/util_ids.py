"""Generate IDs compatible with existing Prisma cuid rows."""

try:
    from cuid import cuid as _cuid

    def new_cuid() -> str:
        return _cuid()

except ImportError:
    import secrets

    def new_cuid() -> str:
        # Fallback — not Prisma-cuid format but unique TEXT id
        return secrets.token_urlsafe(16)
