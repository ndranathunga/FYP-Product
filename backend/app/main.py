from fastapi import FastAPI, HTTPException, Body, Depends
from fastapi.middleware.wsgi import WSGIMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional
import sys
from pathlib import Path
from loguru import logger

from fastapi.responses import RedirectResponse

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
PROJECT_ROOT_FOR_MAIN = BACKEND_DIR.parent
if str(PROJECT_ROOT_FOR_MAIN) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_MAIN))

from backend.app.config import settings
from backend.app.services.model_service import model_service
from backend.app.services.analysis_service import (
    initialize_analysis_service,
    get_analysis_service,
    AnalysisService,
)
from backend.app.prompts.prompt_engine import prompt_engine

try:
    from frontend.dashboard.app import (
        app as dash_app_instance,
    )

    DASH_CONFIGURED_URL_BASE_PATHNAME = dash_app_instance.config.url_base_pathname
    logger.info("Dash app instance imported successfully.")
except ImportError as e:
    logger.error(f"Could not import Dash app (dash_app_instance): {e}", exc_info=True)
    dash_app_instance = None
    DASH_CONFIGURED_URL_BASE_PATHNAME = "N/A (Dash app not loaded)"
except AttributeError:  # Should not happen if Dash app structure is correct
    logger.error(
        "Dash app instance imported, but '.config.url_base_pathname' is missing.",
        exc_info=True,
    )
    dash_app_instance = None  # Treat as not loaded
    DASH_CONFIGURED_URL_BASE_PATHNAME = "N/A (Dash config error)"

app = FastAPI(title="Customer Review Analysis API")
logger.info("Main FastAPI application instance created.")


# --- Pydantic Models ---
class ReviewInput(BaseModel):
    text: str


class AnalysisResult(BaseModel):
    language: Optional[Dict[str, Any]] = None
    sentiment: Optional[Dict[str, Any]] = None


class StatsResponse(BaseModel):
    stats: Optional[Dict[str, Any]] = None


# --- Event Handlers ---
@app.on_event("startup")
async def startup_event():
    logger.info("FastAPI Event: Application startup initiated...")
    await initialize_analysis_service()
    logger.info("FastAPI Event: Application startup complete.")


# --- API Endpoints ---
@app.post("/api/v1/analyze_review", response_model=AnalysisResult)
async def analyze_review_endpoint(review: ReviewInput):
    logger.debug(f"API POST /api/v1/analyze_review with text: '{review.text[:50]}...'")
    if not model_service.language_model or not model_service.sentiment_model:
        logger.error("Models not available for /api/v1/analyze_review")
        raise HTTPException(status_code=503, detail="Models not available.")
    lang_result = await model_service.get_language(review.text)
    sentiment_result = await model_service.get_sentiment(review.text)
    return AnalysisResult(language=lang_result, sentiment=sentiment_result)


@app.get("/api/v1/stats", response_model=StatsResponse)
async def get_statistics_endpoint(
    analysis_svc: AnalysisService = Depends(get_analysis_service),
):
    logger.debug("API GET /api/v1/stats called")
    stats_data = analysis_svc.get_stats()
    if (
        not stats_data
        or stats_data.get("status") == "loading"
        or stats_data.get("error")
    ):
        detail_msg = "Statistics not found or error."
        status_code = 404
        if stats_data:
            detail_msg = stats_data.get("message", detail_msg)
            if stats_data.get("status") == "loading":
                status_code = 202
        raise HTTPException(status_code=status_code, detail=detail_msg)
    return StatsResponse(stats=stats_data)


@app.post("/api/v1/trigger_reanalysis", response_model=StatsResponse)
async def trigger_reanalysis_endpoint(
    analysis_svc: AnalysisService = Depends(get_analysis_service),
):
    logger.info("API POST /api/v1/trigger_reanalysis called.")
    new_stats = await analysis_svc.run_full_analysis()
    return StatsResponse(stats=new_stats)


@app.get("/api/v1/prompt/{prompt_name}")
async def get_prompt_template_endpoint(prompt_name: str, version: Optional[str] = None):
    logger.debug(f"API GET /api/v1/prompt/{prompt_name}. Version: {version}")
    prompt_str = prompt_engine.get_prompt(prompt_name, version=version)
    v = version or settings.prompts.engine.default_version
    if not prompt_str:
        raise HTTPException(
            status_code=404, detail=f"Prompt '{prompt_name}' v'{v}' not found."
        )
    return {"prompt_name": prompt_name, "version": v, "template": prompt_str}


@app.get("/")
async def root():
    logger.debug("API GET / (FastAPI root) called.")
    return {
        "message": "Customer Review Analysis API",
        "api_docs_url": "/docs",
        "dashboard_url": (
            settings.frontend_base_url
            if dash_app_instance and dash_app_instance.server
            else "Dashboard not available"
        ),
    }


# --- Mount Dash App ---
if dash_app_instance and dash_app_instance.server:
    mount_path = settings.frontend_base_url.rstrip("/")  # + "/"
    app.mount(
        mount_path,
        WSGIMiddleware(dash_app_instance.server),
        name="dash_app",
    )
    logger.info(
        f"FastAPI: Dash app mounted at FastAPI path: '{mount_path}' using WSGIMiddleware."
    )
    logger.debug(
        f"FastAPI: Dash app's internal url_base_pathname is: '{DASH_CONFIGURED_URL_BASE_PATHNAME}'"
    )  # Should be /dashboard/

    @app.get(f"{mount_path}/", include_in_schema=False)
    async def _dash_redirect():
        return RedirectResponse(mount_path, status_code=307)

else:
    logger.error(
        "FastAPI: Dash app server not available. Frontend will not be mounted."
    )
