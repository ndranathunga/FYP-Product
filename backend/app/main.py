from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.middleware.wsgi import WSGIMiddleware


import sys
from pathlib import Path
from loguru import logger

from backend.app.config import settings
from backend.app.services.analysis_service import initialize_analysis_service
from backend.app.api.v1.router import api_v1_router

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
PROJECT_ROOT_FOR_MAIN = BACKEND_DIR.parent
if str(PROJECT_ROOT_FOR_MAIN) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_MAIN))


try:
    from frontend.dashboard.app import app as dash_app_instance

    DASH_CONFIGURED_URL_BASE_PATHNAME = dash_app_instance.config.url_base_pathname
    logger.info("Dash app instance imported successfully.")
except ImportError as e:
    logger.error(f"Could not import Dash app (dash_app_instance): {e}", exc_info=True)
    dash_app_instance = None
    DASH_CONFIGURED_URL_BASE_PATHNAME = "N/A (Dash app not loaded)"
except AttributeError:
    logger.error(
        "Dash app instance imported, but '.config.url_base_pathname' is missing.",
        exc_info=True,
    )
    dash_app_instance = None
    DASH_CONFIGURED_URL_BASE_PATHNAME = "N/A (Dash config error)"

app = FastAPI(title="Customer Review Analysis API")
logger.info("Main FastAPI application instance created.")


@app.on_event("startup")
async def startup_event():
    logger.info("FastAPI Event: Application startup initiated...")
    await initialize_analysis_service()
    logger.info("FastAPI Event: Application startup complete.")


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


# --- Root and Health Endpoints ---
@app.get("/")
async def root():
    logger.debug("API GET / (FastAPI root) called.")
    dashboard_url_msg = "Dashboard not available"
    if dash_app_instance and dash_app_instance.server:
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
if dash_app_instance and dash_app_instance.server:
    mount_path = settings.frontend_base_url.rstrip("/")
    app.mount(
        mount_path,
        WSGIMiddleware(dash_app_instance.server),
        name="dash_app",
    )
    logger.info(f"FastAPI: Dash app mounted at FastAPI path: '{mount_path}'")
    logger.debug(
        f"FastAPI: Dash app's internal url_base_pathname is: '{DASH_CONFIGURED_URL_BASE_PATHNAME}'"
    )
    if not mount_path.endswith("/"):

        @app.get(mount_path, include_in_schema=False)
        async def _dash_base_redirect_to_slash():
            return RedirectResponse(url=f"{mount_path}/", status_code=307)

else:
    logger.error(
        "FastAPI: Dash app server not available. Frontend will not be mounted."
    )
