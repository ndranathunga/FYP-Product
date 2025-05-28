from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.middleware.wsgi import WSGIMiddleware


import sys
from pathlib import Path
from loguru import logger

from backend.app.config import settings
from backend.app.services.analysis_service import (
    initialize_analysis_service_dependencies,
)
from backend.app.api.v1.router import api_v1_router
from backend.app.db.connection import initialize_connection_pool, close_connection_pool

from backend.app.api.v1.endpoints.admin_seed_data import router as admin_seed_router

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
PROJECT_ROOT_FOR_MAIN = BACKEND_DIR.parent
if str(PROJECT_ROOT_FOR_MAIN) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_MAIN))

# --- Dash App Import ---
DASH_APP_IS_AVAILABLE = False
DASH_EXPECTED_ROUTE_PREFIX = None

try:
    from frontend.dashboard.app import app as dash_app_instance

    if hasattr(dash_app_instance, "config") and dash_app_instance.config:
        if dash_app_instance.config.get("requests_pathname_prefix"):
            DASH_EXPECTED_ROUTE_PREFIX = (
                dash_app_instance.config.requests_pathname_prefix
            )
            logger.info(
                f"Dash app instance imported successfully. Expected route prefix: '{DASH_EXPECTED_ROUTE_PREFIX}'"
            )
            DASH_APP_IS_AVAILABLE = True
        else:
            logger.error(
                "Dash app instance imported, but '.config.requests_pathname_prefix' is missing or not set."
            )
            dash_app_instance = None
    else:
        logger.error(
            "Dash app instance imported, but '.config' attribute is missing or empty."
        )
        dash_app_instance = None

except ImportError as e:
    logger.error(f"Could not import Dash app (dash_app_instance): {e}", exc_info=True)
    dash_app_instance = None
except Exception as e:
    logger.error(
        f"An unexpected error occurred while importing Dash app: {e}", exc_info=True
    )
    dash_app_instance = None

app = FastAPI(title="Customer Review Analysis API")
logger.info("Main FastAPI application instance created.")


@app.on_event("startup")
async def startup_event():
    logger.info("FastAPI Event: Application startup initiated...")
    try:
        initialize_connection_pool()
        logger.info("Database connection pool initialized successfully.")
    except Exception as e:
        logger.critical(
            f"Failed to initialize database connection pool: {e}", exc_info=True
        )

    await initialize_analysis_service_dependencies()
    logger.info(
        "FastAPI Event: Analysis service dependencies initialized. Application startup complete."
    )


@app.on_event("shutdown")
def shutdown_event():
    logger.info("FastAPI Event: Application shutdown initiated...")
    close_connection_pool()
    logger.info(
        "FastAPI Event: Database connection pool closed. Application shutdown complete."
    )


# --- Auth Related Static HTML Routes ---
@app.get("/auth/signup", include_in_schema=False)
@app.get("/auth/signup/", include_in_schema=False)
async def signup_html_redirect():
    return RedirectResponse(url="signup.html")


@app.get("/auth/login", include_in_schema=False)
@app.get("/auth/login/", include_in_schema=False)
async def login_html_redirect():
    return RedirectResponse(url="login.html")


app.mount(
    "/auth",
    StaticFiles(directory=PROJECT_ROOT_FOR_MAIN / "frontend/auth", html=True),
    name="auth-static",
)

# --- V1 API router ---
app.include_router(api_v1_router, prefix="/api/v1")

app.include_router(admin_seed_router, prefix="/admin", tags=["Admin Seed Data"])

# --- Root and Health Endpoints ---
@app.get("/")
async def root():
    logger.debug("API GET / (FastAPI root) called.")
    dashboard_url_msg = (
        "Dashboard not available (Dash app not configured or failed to load)"
    )
    if DASH_APP_IS_AVAILABLE and dash_app_instance and dash_app_instance.server:
        dashboard_url_msg = settings.frontend_base_url

    return {
        "message": "Customer Review Analysis API",
        "api_docs_url": "/docs",
        "redoc_url": "/redoc",
        "dashboard_url": dashboard_url_msg,
        "health_check": "/health",
    }


@app.get("/health", tags=["Health Check"])
async def health_check():
    return {"status": "ok", "message": "API is healthy"}


# --- Mount Dash App ---
if DASH_APP_IS_AVAILABLE and dash_app_instance and dash_app_instance.server:
    mount_path = settings.frontend_base_url.rstrip("/")

    app.mount(
        mount_path,
        WSGIMiddleware(dash_app_instance.server),
        name="dash_app",
    )
    logger.info(f"FastAPI: Dash app mounted at FastAPI path: '{mount_path}'")
    logger.debug(
        f"FastAPI: Dash app's configured requests_pathname_prefix is: '{DASH_EXPECTED_ROUTE_PREFIX}'"
    )

    if DASH_EXPECTED_ROUTE_PREFIX and DASH_EXPECTED_ROUTE_PREFIX == mount_path + "/":

        @app.get(mount_path, include_in_schema=False)
        async def _dash_base_redirect_to_slash():
            logger.debug(
                f"Redirecting base Dash path from '{mount_path}' to '{DASH_EXPECTED_ROUTE_PREFIX}' for consistency."
            )
            return RedirectResponse(url=DASH_EXPECTED_ROUTE_PREFIX, status_code=307)

else:
    logger.error(
        "FastAPI: Dash app server not available (DASH_APP_IS_AVAILABLE is False or server attribute missing). Frontend will not be mounted."
    )
