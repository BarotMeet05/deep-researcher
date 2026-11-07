"""
FastAPI Application Entrypoint
Configures CORS, security middleware, API routes, and serves the React SPA frontend.
"""
import base64
import logging
from pathlib import Path
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.api.routes import router as api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Autonomous Multi-Step Research Assistant Agent built with LangGraph & Google Gemini.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# 1. CORS Middleware (Must be registered first)
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# ---------------------------------------------------------------------------
# 2. Security Passcode Middleware
# Protects API endpoints and Swagger UI, while allowing static frontend assets.
# ---------------------------------------------------------------------------
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    # Always allow CORS preflights and health checks
    if request.method == "OPTIONS" or request.url.path == "/health":
        return await call_next(request)

    # Only protect API routes and Swagger docs
    is_docs = request.url.path in ("/docs", "/redoc", "/openapi.json")
    is_api = request.url.path.startswith("/api/")

    if not (is_docs or is_api):
        return await call_next(request)

    # If no passcode is set, allow all (open in local dev)
    if not settings.app_access_key:
        return await call_next(request)

    # Extract token from X-App-Key, Bearer, or Basic Auth
    token = request.headers.get("x-app-key")
    auth_header = request.headers.get("authorization", "")

    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif auth_header.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth_header[6:].strip()).decode("utf-8")
            _, password = decoded.split(":", 1)
            token = password
        except Exception:
            pass

    if not token:
        token = request.query_params.get("access_key") or request.query_params.get("key")

    # If token matches, continue
    if token == settings.app_access_key:
        return await call_next(request)

    # For Swagger UI, return Basic Auth challenge so browser pops up login dialog
    if is_docs:
        return Response(
            status_code=401,
            content="Authentication required",
            headers={
                "WWW-Authenticate": 'Basic realm="DeepResearcher Protected API"',
                "Access-Control-Allow-Origin": "*",
            },
        )

    # For API routes, return standard JSON 401
    return JSONResponse(
        status_code=401,
        content={
            "error": "UNAUTHORIZED",
            "message": "Invalid or missing access passcode.",
            "status": 401,
        },
        headers={"Access-Control-Allow-Origin": "*"},
    )


# ---------------------------------------------------------------------------
# 3. Health & API Routes
# ---------------------------------------------------------------------------
@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
        "llm_provider": settings.llm_provider,
        "version": "0.1.0",
    }


app.include_router(api_router)


# ---------------------------------------------------------------------------
# 4. React SPA Static File Serving (Single-Platform Monolith)
# ---------------------------------------------------------------------------
frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if frontend_dist.exists():
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Don't hijack API or docs routes
        if full_path.startswith("api/") or full_path in ("docs", "redoc", "openapi.json", "health"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

        file_path = frontend_dist / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))

        return FileResponse(str(frontend_dist / "index.html"))
else:
    @app.get("/")
    def root_fallback():
        return {
            "app": settings.app_name,
            "status": "online",
            "message": "Frontend build not detected in frontend/dist. In development, run 'npm run dev' in frontend directory.",
        }
