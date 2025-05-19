import uuid
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import Counter
import asyncio
from loguru import logger

from ..config import settings
from ..core import memory_cache as caching
from .model_service import model_service
from ..prompts.prompt_engine import prompt_engine

from ..db import reviews as db_reviews
from ..db import products as db_products
from ..db import analysis_results as db_analysis_results
from ..db.schemas import (
    Review as DBReviewSchema,
    AnalysisResultCreate,
    AnalysisResultItem,
)


class AnalysisService:
    def __init__(self):
        logger.trace("Initializing AnalysisService...")

    async def analyze_and_store_review(
        self, review: DBReviewSchema, user_id: uuid.UUID
    ) -> Optional[AnalysisResultItem]:
        logger.trace(f"Analyzing review ID: {review.id} for user: {user_id}")
        try:
            lang_result = await model_service.get_language(review.review_text)
            sentiment_result = await model_service.get_sentiment(review.review_text)

            if (
                not lang_result
                or lang_result.get("error")
                or not sentiment_result
                or sentiment_result.get("error")
            ):
                logger.error(
                    f"Model prediction failed for review {review.id}. Lang: {lang_result}, Sent: {sentiment_result}"
                )
                return None

            #! FIXME: This is a placeholder for the actual logic to create an analysis result.
            analysis_create_data = AnalysisResultCreate(
                review_id=review.id,
                language=lang_result.get("language"),
                sentiment=sentiment_result.get(
                    "stars"
                ),  # Assuming 'stars' is the sentiment score
                confidence=sentiment_result.get(
                    "confidence"
                ),  # Or combine lang/sent confidence
                result_json={
                    "language_model_output": lang_result,
                    "sentiment_model_output": sentiment_result,
                },
            )

            stored_analysis = db_analysis_results.create_analysis_result_db(
                analysis_create_data
            )

            if stored_analysis:
                logger.success(
                    f"Analysis for review {review.id} stored/updated: {stored_analysis.id}"
                )
                # Invalidate this user's stats cache as new data is available
                cache_key = f"stats_{user_id}"
                if cache_key in caching.user_stats_cache:
                    try:
                        del caching.user_stats_cache[cache_key]
                        logger.debug(
                            f"Invalidated stats cache for user {user_id} due to new analysis for review {review.id}."
                        )
                    except KeyError:  # pragma: no cover
                        logger.warning(
                            f"Cache key {cache_key} already removed for user {user_id}, possibly by another concurrent task."
                        )
                return stored_analysis
            else:  # pragma: no cover
                logger.error(
                    f"Failed to store analysis for review {review.id} after model prediction."
                )
                return None

        except Exception as e:
            logger.error(
                f"Exception during analysis/storage for review {review.id}: {e}",
                exc_info=True,
            )
            return None

    async def run_bulk_analysis_for_user(self, user_id: uuid.UUID) -> Dict[str, Any]:
        logger.trace(f"Starting bulk analysis for user_id: {user_id}...")
        user_reviews = db_reviews.get_all_reviews_for_user_db(user_id)

        if not user_reviews:
            logger.warning(f"No reviews found for user {user_id} to analyze.")
            return await self.get_user_stats(user_id)

        tasks = []
        for review_obj in user_reviews:
            tasks.append(self.analyze_and_store_review(review_obj, user_id))

        logger.info(
            f"Processing {len(tasks)} reviews concurrently for user {user_id}..."
        )
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful_processing_count = 0
        failed_processing_count = 0
        for i, result_item in enumerate(results):
            if isinstance(result_item, Exception):  # pragma: no cover
                logger.error(
                    f"Error processing review task (index {i}) for user {user_id}: {result_item}",
                    exc_info=result_item,
                )
                failed_processing_count += 1
            elif result_item:  # If an AnalysisResultItem was returned
                successful_processing_count += 1
            else:
                failed_processing_count += 1

        logger.info(
            f"Bulk analysis for user {user_id}: Successfully processed {successful_processing_count}/{len(tasks)} reviews. Failed: {failed_processing_count}."
        )

        return await self.get_user_stats(user_id)

    async def get_user_stats(self, user_id: uuid.UUID) -> Dict[str, Any]:
        cache_key = f"stats_{user_id}"
        try:
            cached_stats = caching.user_stats_cache[cache_key]
            logger.debug(f"Returning cached stats for user {user_id}")
            return cached_stats
        except KeyError:
            logger.trace(f"No cache found for user {user_id}. Computing stats from DB.")
            pass  # Cache miss, proceed to compute

        try:
            total_processed = (
                db_analysis_results.get_total_reviews_processed_for_user_db(user_id)
            )
            total_in_dataset = (
                db_analysis_results.get_total_reviews_in_dataset_for_user_db(user_id)
            )

            summary_data = db_analysis_results.get_user_stats_summary_db(user_id)

            # TODO: Proper analysis implementation here
            language_counts = Counter()
            overall_sentiment_counts = (
                Counter()
            )  # Stores counts for each sentiment value (e.g., stars)
            sentiment_by_language = {}  # lang -> Counter(sentiment_value -> count)

            for row in summary_data:
                lang = row.get("language")
                sentiment_val = row.get("sentiment")  # This is the 'stars' (integer)
                count = row.get("count", 0)

                if lang:  # Only count if language is present
                    language_counts[lang] += count

                if sentiment_val is not None:  # Ensure sentiment is not NULL
                    overall_sentiment_counts[
                        str(sentiment_val)
                    ] += count  # Convert sentiment to string for consistent dict keys
                    if lang:  # Only add to sentiment_by_language if language is present
                        if lang not in sentiment_by_language:
                            sentiment_by_language[lang] = Counter()
                        sentiment_by_language[lang][str(sentiment_val)] += count

            stats = {
                "total_reviews_processed": total_processed,
                "total_reviews_in_dataset": total_in_dataset,
                "language_distribution": dict(language_counts),
                "overall_sentiment_distribution": dict(overall_sentiment_counts),
                "sentiment_distribution_by_language": {
                    lang: dict(counts) for lang, counts in sentiment_by_language.items()
                },
            }
            caching.user_stats_cache[cache_key] = stats
            logger.success(f"Computed and cached stats for user {user_id}")
            return stats
        except Exception as e:  # pragma: no cover
            logger.error(
                f"Error computing stats for user {user_id}: {e}", exc_info=True
            )
            return {"error": f"Could not compute stats for user {user_id}: {str(e)}"}


_analysis_service_instance: Optional[AnalysisService] = None


async def initialize_analysis_service():
    global _analysis_service_instance

    logger.debug("Attempting to initialize AnalysisService...")
    if _analysis_service_instance is None:
        logger.debug("AnalysisService instance not found, creating new one.")
        _analysis_service_instance = AnalysisService()
        logger.trace("AnalysisService initialized.")
    else:
        logger.debug("AnalysisService instance already exists.")

    return _analysis_service_instance


def get_analysis_service() -> AnalysisService:
    if _analysis_service_instance is None:
        logger.critical("AnalysisService accessed before async initialization!")
        raise RuntimeError(
            "AnalysisService not initialized. Ensure initialize_analysis_service() is awaited at application startup."
        )
    return _analysis_service_instance
