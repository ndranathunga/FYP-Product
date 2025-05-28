# backend/app/services/analysis_service.py
import uuid
from typing import List, Dict, Any, Optional
from collections import Counter, defaultdict
import asyncio
from loguru import logger
from starlette.concurrency import run_in_threadpool
import json  # For json.dumps when storing, and json.loads if DB returns string
import ast  # For parsing Python dict-like strings from result_json if necessary

from backend.app.config import settings
from .model_service import model_service

from backend.app.db.reviews import get_all_reviews_with_product_info_for_user_db
from backend.app.db.analysis_results import (
    create_analysis_result_db,
    get_analysis_result_by_review_id_db,
)
from backend.app.db.schemas import (
    AnalysisResultCreate,
    AnalysisResultItem,
    Review as ReviewSchema,
)


class AnalysisService:
    def __init__(self):
        logger.info("Initializing User-Specific AnalysisService (using db module)...")
        self.user_stats: Dict[str, Dict[str, Any]] = {}
        self._user_stats_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._user_stats_ready_events: Dict[str, asyncio.Event] = defaultdict(
            asyncio.Event
        )
        logger.debug("User-Specific AnalysisService initialized.")

    async def _parse_result_json_from_db(
        self, result_json_db_val: Any, review_id_for_log: str
    ) -> Optional[Dict[str, Any]]:
        """
        Safely parses result_json which might be a dict (ideal from JSONB) or a string.
        If string, attempts ast.literal_eval.
        """
        method_name = "AnalysisService._parse_result_json_from_db"
        if isinstance(result_json_db_val, dict):
            return result_json_db_val
        if isinstance(result_json_db_val, str):
            try:
                logger.debug(
                    f"{method_name}: Attempting ast.literal_eval for review {review_id_for_log} on DB string: {result_json_db_val[:100]}..."
                )
                # This string MUST be a valid Python literal (e.g., internal ' in strings escaped as \\')
                parsed_dict = ast.literal_eval(result_json_db_val)
                if isinstance(parsed_dict, dict):
                    return parsed_dict
                else:
                    logger.warning(
                        f"{method_name}: ast.literal_eval on DB string for review {review_id_for_log} did not yield a dict (type: {type(parsed_dict).__name__})."
                    )
                    return None  # Or an error dict: {"error": "Stored analysis string parsed to non-dict"}
            except (SyntaxError, ValueError) as e:
                logger.warning(
                    f"{method_name}: ast.literal_eval FAILED for review {review_id_for_log} on DB string. Error: {e}. String (repr): {repr(result_json_db_val)}",
                    exc_info=True,
                )
                return None  # Or an error dict
        logger.warning(
            f"{method_name}: Stored result_json for review {review_id_for_log} is neither dict nor string (type: {type(result_json_db_val).__name__})."
        )
        return None

    async def _populate_user_stats_from_database(
        self, user_id: uuid.UUID, force_refresh: bool = False
    ):
        user_id_str = str(user_id)
        method_name = f"AnalysisService._populate_user_stats_from_database(user='{user_id_str}', force={force_refresh})"

        async with self._user_stats_locks[user_id_str]:
            if (
                not force_refresh
                and self.user_stats.get(user_id_str)
                and self._user_stats_ready_events[user_id_str].is_set()
                and self.user_stats[user_id_str].get("status") == "loaded"
            ):
                logger.debug(f"{method_name}: Stats already populated. Skipping.")
                return

            logger.info(f"{method_name}: Starting population/refresh...")
            self._user_stats_ready_events[user_id_str].clear()
            self.user_stats[user_id_str] = {
                "status": "loading",
                "products_data": {},
                "message": f"Initializing stats for user {user_id_str}...",
            }

            try:
                reviews_from_db: List[Dict[str, Any]] = await run_in_threadpool(
                    get_all_reviews_with_product_info_for_user_db, user_id
                )
            except Exception as e_db_fetch:  # Catch specific DB errors if possible
                error_msg = f"Database error fetching reviews for user {user_id_str}: {e_db_fetch}"
                logger.error(f"{method_name}: {error_msg}", exc_info=True)
                self.user_stats[user_id_str] = {
                    "status": "error",
                    "message": error_msg,
                    "products_data": {},
                }
                self._user_stats_ready_events[user_id_str].set()
                return

            if not reviews_from_db:
                # ... (same handling for no reviews)
                info_msg = f"No reviews found in database for user {user_id_str}. Product statistics will be empty."
                logger.info(f"{method_name}: {info_msg}")
                self.user_stats[user_id_str] = {
                    "status": "loaded",
                    "message": info_msg,
                    "products_data": {},
                    "total_reviews_processed_this_user": 0,
                    "total_reviews_in_dataset_this_user": 0,
                }
                self._user_stats_ready_events[user_id_str].set()
                return

            tasks = [
                self._process_single_review_for_aggregation(r, force_refresh)
                for r in reviews_from_db
            ]
            logger.info(
                f"{method_name}: Processing {len(tasks)} reviews for aggregation..."
            )
            processed_review_results = await asyncio.gather(
                *tasks, return_exceptions=True
            )

            analyses_for_aggregation: List[Dict[str, Any]] = []
            for i, res_or_exc in enumerate(processed_review_results):
                original_review_id = str(
                    reviews_from_db[i].get("review_id", "UNKNOWN_ID")
                )
                if isinstance(
                    res_or_exc, Exception
                ):  # Exception from _process_single_review_for_aggregation
                    logger.error(
                        f"{method_name}: Exception processing review ID {original_review_id}: {res_or_exc}",
                        exc_info=res_or_exc,
                    )
                elif (
                    res_or_exc
                    and res_or_exc.get("error")
                    and "No analysis data available" not in res_or_exc.get("error", "")
                ):
                    # Log actual errors, not just "skipped because not forced"
                    logger.warning(
                        f"{method_name}: Failed to get aspect data for review ID {original_review_id}: {res_or_exc.get('error')}"
                    )
                elif res_or_exc and isinstance(
                    res_or_exc.get("aspects_data"), list
                ):  # Successfully processed or intentionally skipped (empty aspects_data)
                    analyses_for_aggregation.append(res_or_exc)
                else:
                    logger.warning(
                        f"{method_name}: Unexpected result for review ID {original_review_id}: {str(res_or_exc)[:200]}"
                    )

            logger.info(
                f"{method_name}: Gathered data for {len(analyses_for_aggregation)} reviews (some may have empty aspects if not analyzed/forced)."
            )

            product_aggregation = defaultdict(
                lambda: {
                    "product_id": None,
                    "product_name": None,
                    "total_reviews_analyzed": 0,
                    "aspect_details": defaultdict(
                        lambda: {
                            "sum_ratings": 0,
                            "count": 0,
                            "distribution": Counter(),
                        }
                    ),
                }
            )
            for analysis_output in analyses_for_aggregation:
                if not analysis_output.get(
                    "aspects_data"
                ):  # Skip if aspects_data is empty (e.g., review not analyzed and not forced)
                    continue
                pid = str(analysis_output["product_id"])
                pname = analysis_output.get("product_name", pid)
                product_aggregation[pid]["product_id"] = pid
                product_aggregation[pid]["product_name"] = pname
                product_aggregation[pid]["total_reviews_analyzed"] += 1
                for aspect_item in analysis_output.get("aspects_data", []):
                    aspect_name = aspect_item.get("name")
                    aspect_rating = aspect_item.get("rating")
                    if (
                        aspect_name
                        and isinstance(aspect_rating, (int, float))
                        and aspect_rating > 0
                    ):
                        agg_aspect = product_aggregation[pid]["aspect_details"][
                            aspect_name
                        ]
                        agg_aspect["sum_ratings"] += aspect_rating
                        agg_aspect["count"] += 1
                        agg_aspect["distribution"][int(aspect_rating)] += 1

            final_products_payload = {}
            for pid, agg_data in product_aggregation.items():
                product_aspects_summary = {}
                for aspect_name, data in agg_data["aspect_details"].items():
                    string_keyed_distribution = {
                        str(r): c for r, c in data["distribution"].items()
                    }
                    product_aspects_summary[aspect_name] = {
                        "average_rating": (
                            round(data["sum_ratings"] / data["count"], 2)
                            if data["count"] > 0
                            else 0
                        ),
                        "review_count": data["count"],
                        "rating_distribution": string_keyed_distribution,
                    }
                current_ratings_for_dashboard = {
                    name: details["average_rating"]
                    for name, details in product_aspects_summary.items()
                }
                dashboard_summary_obj = {
                    "Current Ratings": current_ratings_for_dashboard,
                    "Summary Ratings": current_ratings_for_dashboard,
                    "Summary": f"Aggregated insights for {agg_data.get('product_name', 'this product')}.",
                    "Recommendations": "Review aspects with lower ratings.",
                    "Anomaly": False,
                }
                final_products_payload[pid] = {
                    "product_id": pid,
                    "product_name": agg_data.get("product_name", pid),
                    "total_reviews_analyzed": agg_data.get("total_reviews_analyzed", 0),
                    "aspects_summary": product_aspects_summary,
                    "dashboard_summary": dashboard_summary_obj,
                }

            final_message = f"Statistics for user {user_id_str} loaded successfully."
            if not final_products_payload and reviews_from_db:
                final_message = f"User {user_id_str} has reviews, but no aspect data was found/generated for summaries (check if reviews are analyzed)."

            self.user_stats[user_id_str] = {
                "products_data": final_products_payload,
                "total_reviews_processed_this_user": sum(
                    p["total_reviews_analyzed"] for p in final_products_payload.values()
                ),
                "total_reviews_in_dataset_this_user": len(reviews_from_db),
                "status": "loaded",
                "message": final_message,
            }
            logger.success(
                f"{method_name}: Stats populated. {len(final_products_payload)} products have aggregated data."
            )
            self._user_stats_ready_events[user_id_str].set()

    async def _process_single_review_for_aggregation(
        self, review_item_from_db: Dict[str, Any], force_model_reanalysis: bool = False
    ) -> Dict[str, Any]:
        method_name = "AnalysisService._process_single_review_for_aggregation"
        review_id_str = str(review_item_from_db.get("review_id"))
        try:
            review_id_uuid = uuid.UUID(review_id_str)
        except ValueError:
            logger.warning(
                f"{method_name}: Invalid UUID format for review_id: '{review_id_str}'"
            )
            return {
                "error": "Invalid review_id format",
                "review_id": review_id_str,
                "aspects_data": [],
            }

        product_id_str = str(review_item_from_db.get("product_id"))
        pname = str(review_item_from_db.get("product_name", product_id_str))
        review_text = review_item_from_db.get("review_text", "").strip()

        if not review_text:
            return {
                "error": "Empty review text",
                "review_id": review_id_str,
                "product_id": product_id_str,
                "product_name": pname,
                "aspects_data": [],
            }

        logger.trace(
            f"{method_name}: Processing review ID {review_id_str}, ForceReanalysis: {force_model_reanalysis}"
        )

        analysis_model_output_dict: Optional[Dict[str, Any]] = None
        analysis_source_is_db = False

        # --- Step 1: Try to get analysis from Database ---
        if (
            not force_model_reanalysis
        ):  # Only check DB if we are NOT forcing a model call
            logger.debug(
                f"{method_name}: Not forcing reanalysis for review {review_id_str}. Checking DB for stored analysis."
            )
            stored_item_schema: Optional[AnalysisResultItem] = await run_in_threadpool(
                get_analysis_result_by_review_id_db, review_id_uuid
            )
            if stored_item_schema and stored_item_schema.result_json:
                # result_json from Pydantic schema should already be a Dict[str, Any]
                # No need for _parse_result_json_from_db helper if schemas are correct
                parsed_from_db = stored_item_schema.result_json
                if (
                    parsed_from_db
                    and "aspects" in parsed_from_db
                    and isinstance(parsed_from_db.get("aspects"), list)
                ):
                    analysis_model_output_dict = parsed_from_db
                    analysis_source_is_db = True
                    logger.debug(
                        f"{method_name}: Used valid stored analysis from DB for review ID {review_id_str}."
                    )
                else:
                    logger.warning(
                        f"{method_name}: Stored analysis for review {review_id_str} in DB is malformed or missing 'aspects'. It will be skipped for current aggregation unless re-analysis is forced."
                    )
            else:
                logger.debug(
                    f"{method_name}: No analysis found in DB for review {review_id_str}."
                )

        # --- Step 2: If forcing reanalysis OR (it's a new review for analyze_and_store_single_review which forces) ---
        # The analyze_and_store_single_review method calls this with force_model_reanalysis=True
        if force_model_reanalysis:
            if not settings.models.sentiment:  # Check if model is configured
                logger.warning(
                    f"{method_name}: Sentiment model not configured. Cannot re-analyze review {review_id_str}."
                )
                # If analysis was found in DB before this check, we could still use it, but force_model_reanalysis implies we shouldn't.
                # So, if model is not configured and reanalysis is forced, we have no data.
                return {
                    "error": "Sentiment model not configured for forced reanalysis",
                    "review_id": review_id_str,
                    "product_id": product_id_str,
                    "product_name": pname,
                    "aspects_data": [],
                }

            logger.info(
                f"{method_name}: Force re-analyzing review {review_id_str} with model (or initial analysis)."
            )
            model_call_result = await model_service.get_sentiment(review_text)

            if not model_call_result or model_call_result.get("error"):
                err = (
                    model_call_result.get("error", "Model error")
                    if model_call_result
                    else "Model call returned None"
                )
                logger.warning(
                    f"{method_name}: Model call failed for review {review_id_str} during reanalysis: {err}"
                )
                return {
                    "error": f"Model reanalysis failed: {err}",
                    "review_id": review_id_str,
                    "product_id": product_id_str,
                    "product_name": pname,
                    "aspects_data": [],
                }

            analysis_model_output_dict = (
                model_call_result  # Should be {"aspects": [...]}
            )
            logger.info(
                f"{method_name}: Successfully received model output for review {review_id_str} during reanalysis."
            )

            analysis_to_store = AnalysisResultCreate(
                review_id=review_id_uuid, result_json=analysis_model_output_dict
            )
            db_save_status = await run_in_threadpool(
                create_analysis_result_db, analysis_to_store
            )
            if db_save_status:
                logger.info(
                    f"{method_name}: Stored/Updated model analysis for review {review_id_str} in DB."
                )
            else:
                logger.warning(
                    f"{method_name}: Failed to store/update model analysis for review {review_id_str} in DB after reanalysis."
                )

        # --- Step 3: Final Check and Return ---
        if not analysis_model_output_dict:
            # This path is hit if:
            # - force_model_reanalysis was False, AND analysis was not in DB (or was malformed)
            # - force_model_reanalysis was True, BUT model was not configured (edge case)
            logger.debug(
                f"{method_name}: No valid analysis data available for review {review_id_str} for this aggregation pass."
            )
            return {
                # Not an "error" in the sense of failure, but indicates data isn't there for aggregation
                # "error": "No analysis data available or generated for this review in current context.",
                "review_id": review_id_str,
                "product_id": product_id_str,
                "product_name": pname,
                "aspects_data": [],  # Crucial: empty list for aggregation logic to handle gracefully
            }

        # Validate the structure of the analysis_model_output_dict we are about to use
        if "aspects" not in analysis_model_output_dict or not isinstance(
            analysis_model_output_dict.get("aspects"), list
        ):
            logger.warning(
                f"{method_name}: Final analysis data for review {review_id_str} is malformed (missing/invalid 'aspects' list). Source: {'DB' if analysis_source_is_db else 'Model'}. Data: {str(analysis_model_output_dict)[:200]}..."
            )
            return {
                "error": "Malformed final analysis data structure",
                "review_id": review_id_str,
                "product_id": product_id_str,
                "product_name": pname,
                "aspects_data": [],
            }

        return {
            "review_id": review_id_str,
            "product_id": product_id_str,
            "product_name": pname,
            "aspects_data": analysis_model_output_dict["aspects"],
            "raw_model_output": analysis_model_output_dict,
        }

    async def get_user_product_stats(self, user_id: uuid.UUID) -> Dict[str, Any]:
        # ... (Same as your last version - it correctly calls _populate_user_stats_from_database)
        user_id_str = str(user_id)
        _ = self._user_stats_locks[user_id_str]
        _ = self._user_stats_ready_events[user_id_str]
        if not self._user_stats_ready_events[user_id_str].is_set():
            logger.info(
                f"Stats for user {user_id_str} not ready or cache invalidated, triggering population..."
            )
            await self._populate_user_stats_from_database(user_id, force_refresh=False)
            await self._user_stats_ready_events[user_id_str].wait()
            logger.debug(
                f"Stats population for user {user_id_str} complete (or waited for completion)."
            )
        return self.user_stats.get(
            user_id_str,
            {
                "status": "error",
                "message": f"Stats data unavailable for user {user_id_str}.",
                "products_data": {},
            },
        )

    async def trigger_user_reanalysis(self, user_id: uuid.UUID):
        # ... (Same as your last version - correctly schedules background task)
        user_id_str = str(user_id)
        logger.info(f"Triggering background full re-analysis for user {user_id_str}...")
        self._user_stats_ready_events[user_id_str].clear()
        asyncio.create_task(
            self._populate_user_stats_from_database(user_id, force_refresh=True)
        )
        logger.info(f"Background re-analysis task for user {user_id_str} scheduled.")

    async def analyze_single_text_ad_hoc(
        self, review_text: str, product_id_context: Optional[str] = "ad_hoc_product"
    ) -> Dict[str, Any]:
        # ... (Same as your last version - this is for ad-hoc and doesn't touch user stats directly)
        logger.info(
            f"Performing ad-hoc analysis for text (context: {product_id_context}): '{review_text[:50]}...'"
        )
        model_output_or_error = await model_service.get_sentiment(review_text)
        if not model_output_or_error or model_output_or_error.get("error"):
            err_msg = (
                model_output_or_error.get("error", "Ad-hoc model call failed")
                if model_output_or_error
                else "Ad-hoc model call failed"
            )
            return {
                "error": err_msg,
                "review_id": "ad_hoc_review",
                "product_id": product_id_context,
            }
        if "aspects" not in model_output_or_error or not isinstance(
            model_output_or_error.get("aspects"), list
        ):
            return {
                "error": "Ad-hoc model response malformed.",
                "raw_model_output": model_output_or_error,
                "review_id": "ad_hoc_review",
                "product_id": product_id_context,
            }
        return {
            "review_id": "ad_hoc_review",
            "product_id": product_id_context,
            "product_name": product_id_context,
            "aspects_data": model_output_or_error["aspects"],
            "raw_model_output": model_output_or_error,
            "error": None,
        }

    async def analyze_and_store_single_review(
        self, review_schema_item: ReviewSchema, user_id_for_context: uuid.UUID
    ):
        # ... (Same as your last version - correctly calls _process_single_review_for_aggregation with force_model_reanalysis=True)
        method_name = "AnalysisService.analyze_and_store_single_review"
        logger.info(
            f"{method_name}: BG task for review ID {review_schema_item.id}, user {user_id_for_context}"
        )
        review_item_for_processing = {
            "review_id": str(review_schema_item.id),
            "review_text": review_schema_item.review_text,
            "product_id": str(review_schema_item.product_id),
            "product_name": f"Product_{review_schema_item.product_id}",
        }
        processing_result = await self._process_single_review_for_aggregation(
            review_item_from_db=review_item_for_processing, force_model_reanalysis=True
        )
        if processing_result and not processing_result.get("error"):
            logger.info(
                f"{method_name}: BG task for review {review_schema_item.id} analysis successful and stored."
            )
            user_id_str = str(user_id_for_context)
            if user_id_str in self._user_stats_ready_events:
                self._user_stats_ready_events[user_id_str].clear()
            logger.info(
                f"{method_name}: Stats for user {user_id_str} marked for refresh due to new/updated review analysis."
            )
        else:
            error_detail = (
                processing_result.get("error", "Unknown error")
                if processing_result
                else "Unknown processing error"
            )
            logger.error(
                f"{method_name}: BG task for review {review_schema_item.id} analysis FAILED: {error_detail}"
            )


# --- Service Singleton Management (remains the same) ---
_analysis_service_instance: Optional[AnalysisService] = None
_service_creation_lock = asyncio.Lock()


async def get_analysis_service_instance() -> AnalysisService:
    global _analysis_service_instance
    if _analysis_service_instance is None:
        async with _service_creation_lock:
            if _analysis_service_instance is None:
                _analysis_service_instance = AnalysisService()
    return _analysis_service_instance


async def initialize_analysis_service_dependencies():
    await get_analysis_service_instance()
    logger.info(
        "User-specific AnalysisService singleton instance ensured. Stats will be loaded on per-user demand via API calls."
    )
