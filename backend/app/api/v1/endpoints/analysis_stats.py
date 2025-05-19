import uuid
from loguru import logger
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks

from backend.app.auth.deps import get_current_user
from backend.app.services.model_service import model_service
from backend.app.services.analysis_service import get_analysis_service, AnalysisService
from backend.app.db import (
    schemas as db_schemas,
) 
from backend.app.api.v1.schemas import AdhocReviewInput, AdhocAnalysisResult, StatsResponse


router = APIRouter()


@router.post(
    "/analyze_adhoc_review",
    response_model=AdhocAnalysisResult,
    summary="Analyze review text without saving",
)
async def analyze_adhoc_review_endpoint(
    review_input: AdhocReviewInput,
    current_user: dict = Depends(get_current_user),  
):
    user_email = current_user.get("email")
    logger.debug(
        f"API POST /analyze_adhoc_review for user {user_email} with text: '{review_input.text[:50]}...'"
    )
    
    if not model_service.language_model or not model_service.sentiment_model:
        logger.error("Models not available for /analyze_adhoc_review")
        raise HTTPException(status_code=503, detail="Models not available.")
    
    lang_result = await model_service.get_language(review_input.text)
    sentiment_result = await model_service.get_sentiment(review_input.text)
    
    return AdhocAnalysisResult(language=lang_result, sentiment=sentiment_result)


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Get analysis statistics for the current user",
)
async def get_statistics_endpoint(
    analysis_svc: AnalysisService = Depends(get_analysis_service),
    current_user: dict = Depends(get_current_user),
):
    user_id_from_token = uuid.UUID(current_user.get("user_id"))
    logger.debug(f"API GET /stats called for user {user_id_from_token}")
    stats_data = await analysis_svc.get_user_stats(user_id=user_id_from_token)

    if not stats_data or stats_data.get("error"):
        detail_msg = "Statistics not found or error computing them."
        status_code = 404
        if stats_data and stats_data.get("error"):
            detail_msg = stats_data.get("error")
        raise HTTPException(status_code=status_code, detail=detail_msg)
    
    return StatsResponse(stats=stats_data)


@router.post(
    "/trigger_user_reanalysis",
    response_model=StatsResponse,
    summary="Trigger re-analysis for all user's reviews",
)
async def trigger_user_reanalysis_endpoint(
    analysis_svc: AnalysisService = Depends(get_analysis_service),
    current_user: dict = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    user_id_from_token = uuid.UUID(current_user.get("user_id"))
    logger.info(
        f"API POST /trigger_user_reanalysis called for user {user_id_from_token}."
    )

    background_tasks.add_task(
        analysis_svc.run_bulk_analysis_for_user, user_id_from_token
    )

    return StatsResponse(
        stats={
            "status": "Reanalysis triggered",
            "message": f"Re-analysis for user {user_id_from_token} has been initiated in the background. Statistics will update shortly.",
        }
    )
