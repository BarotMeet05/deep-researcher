"""
FastAPI Application Entrypoint
Configures CORS, security middleware, and routes.
"""
import base64
import logging
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
# ---------------------------------------------------------------------------
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    # Always allow CORS preflights and health checks
    if request.method == "OPTIONS" or request.url.path == "/health":
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
    if request.url.path in ("/docs", "/redoc", "/openapi.json"):
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
        "version": "0.1.0",
    }


app.include_router(api_router)
