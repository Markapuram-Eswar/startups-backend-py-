from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from app.config import settings
from app.routes.auth import router as auth_router
from app.routes.media import router as media_router
from app.routes.startups import router as startups_router
from app.routes.uploads import router as uploads_router

app = FastAPI(title="Startup FastAPI Backend", version="1.0.0")

def _origins() -> list[str]:
    base = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "https://startups.iittnif.com",
        "https://www.startups.iittnif.com",
        "https://api.startups.iittnif.com",
    ]
    fu = (settings.frontend_url or "").strip().rstrip("/").lower()
    if fu and fu not in [x.lower() for x in base]:
        base.append((settings.frontend_url or "").strip().rstrip("/"))
    return base


allowed_origins = _origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "admin-key"],
)

app.include_router(auth_router)
app.include_router(uploads_router)
app.include_router(media_router)
app.include_router(startups_router)


@app.get("/", response_class=PlainTextResponse)
async def root() -> str:
    return "API running from FastAPI"


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error", "detail": str(exc)},
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
            "Access-Control-Allow-Credentials": "true",
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)},
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
            "Access-Control-Allow-Credentials": "true",
        }
    )
