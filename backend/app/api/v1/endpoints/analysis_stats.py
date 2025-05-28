# backend/app/api/v1/endpoints/analysis_stats.py
import uuid
from loguru import logger
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks

from backend.app.auth.deps import get_current_user
from backend.app.services.analysis_service import (
    get_analysis_service_instance,
    AnalysisService,
)
from backend.app.api.v1.schemas import (
    AdhocReviewInput,
    AdhocAspectAnalysisResult,
    UserProductsStatsResponse,
)

router = APIRouter()


@router.post(
    "/analyze_adhoc_review",
    response_model=AdhocAspectAnalysisResult,
    summary="Analyze review text using aspect model (no saving)",
)
async def analyze_adhoc_review_endpoint(
    review_input: AdhocReviewInput,
    analysis_svc: AnalysisService = Depends(get_analysis_service_instance),
    current_user: dict = Depends(get_current_user),
):
    user_email = current_user.get("email")
    logger.debug(
        f"API POST /analyze_adhoc_review for user {user_email} with text: '{review_input.text[:50]}...' context: {review_input.product_id_context}"
    )
    analysis_result = await analysis_svc.analyze_single_text_ad_hoc(
        review_text=review_input.text,
        product_id_context=review_input.product_id_context,
    )
    if analysis_result.get("error"):
        logger.error(f"Adhoc analysis failed: {analysis_result.get('error')}")
        raise HTTPException(
            status_code=500,
            detail=analysis_result.get("error", "Adhoc analysis failed"),
        )
    return AdhocAspectAnalysisResult(**analysis_result)


@router.get(
    "/stats",
    response_model=UserProductsStatsResponse,
    summary="Get analysis statistics for the current user's products",
)
async def get_user_statistics_endpoint(
    analysis_svc: AnalysisService = Depends(get_analysis_service_instance),
    current_user: dict = Depends(get_current_user),
):
    user_id_from_token = uuid.UUID(current_user.get("user_id"))
    logger.debug(f"API GET /stats called for user {user_id_from_token}")

    user_stats_payload = await analysis_svc.get_user_product_stats(
        user_id=user_id_from_token
    )

    if not user_stats_payload:
        logger.error(f"Stats service returned None for user {user_id_from_token}.")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics.")

    response_data = UserProductsStatsResponse(**user_stats_payload)

    if response_data.status == "error":
        logger.error(
            f"Error state reported by statistics service for user {user_id_from_token}: {response_data.message}"
        )
        raise HTTPException(
            status_code=503,
            detail=response_data.message or "Error retrieving user statistics.",
        )

    logger.info(
        f"Returning stats for user {user_id_from_token} with status: {response_data.status}"
    )
    return response_data


@router.post(
    "/trigger_user_reanalysis",
    response_model=UserProductsStatsResponse,
    summary="Trigger re-analysis for all reviews of the current user",
)
async def trigger_user_reanalysis_endpoint(
    analysis_svc: AnalysisService = Depends(get_analysis_service_instance),
    current_user: dict = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    user_id_from_token = uuid.UUID(current_user.get("user_id"))
    logger.info(
        f"API POST /trigger_user_reanalysis called for user {user_id_from_token}."
    )
    background_tasks.add_task(analysis_svc.trigger_user_reanalysis, user_id_from_token)
    return UserProductsStatsResponse(
        products_data={},
        status="triggered",
        message=f"Re-analysis for user {user_id_from_token} has been initiated. Statistics will update.",
    )
