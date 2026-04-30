from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "startup-pybackend"
    host: str = "0.0.0.0"
    port: int = 8000

    # Prefer DATABASE_URL; else DB_* pieces (matches Node backend/src/config/databaseUrl.js)
    database_url: str | None = None
    db_host: str | None = None
    db_port: str = "5432"
    db_user: str | None = None
    db_password: str | None = None
    db_name: str | None = None
    db_sslmode: str = "require"
    db_ssl_reject_unauthorized: bool = True

    jwt_secret: str = "dev-only-change-me"
    admin_key: str | None = None

    frontend_url: str = "http://localhost:5173"

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_pass: str | None = None
    smtp_from_email: str | None = None
    smtp_from_name: str = "IITTNiF"

    show_otp_in_response: bool = False

    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str = "ap-south-1"
    s3_bucket_name: str | None = None
    s3_bucket_region: str | None = None
    s3_public_base_url: str | None = None
    s3_presigned_get_seconds: int | None = None  # None = default 3600 when bucket set

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()
