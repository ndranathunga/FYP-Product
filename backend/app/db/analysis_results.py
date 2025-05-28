# backend/app/db/analysis_results.py
from datetime import datetime
import uuid
import json
from typing import List, Optional, Dict, Any
from loguru import logger

from .connection import fetch_one, fetch_all, execute_and_fetch_one
from .schemas import AnalysisResultCreate, AnalysisResultItem


def create_analysis_result_db(
    result: AnalysisResultCreate,
    created_at_override: Optional[datetime] = None,  # Optional override
    updated_at_override: Optional[datetime] = None,  # Optional override
) -> Optional[AnalysisResultItem]:

    created_val = "%s" if created_at_override else "timezone('utc'::text, now())"
    updated_val = "%s" if updated_at_override else "timezone('utc'::text, now())"

    query = f"""
    INSERT INTO analysis_results (review_id, result_json, created_at, updated_at)
    VALUES (%s, %s, {created_val}, {updated_val})
    ON CONFLICT (review_id) DO UPDATE SET
        result_json = EXCLUDED.result_json,
        updated_at = {updated_val} -- Use EXCLUDED.updated_at if you want to keep original update time on conflict
    RETURNING id, review_id, result_json, created_at, updated_at;
    """

    params = [
        str(result.review_id),
        json.dumps(result.result_json),
    ]  # Ensure result_json is a string
    if created_at_override:
        params.append(created_at_override)
    if updated_at_override:  # This param is for both INSERT and ON CONFLICT UPDATE path
        params.append(updated_at_override)
    # If created_at_override is None but updated_at_override is present (for INSERT path)
    # and the created_val part of the query is using now(), there's a mismatch in %s count.
    # Simpler: always provide both if overriding, or neither.
    # Let's refine for clarity assuming if one override is given, both should be for consistency during seeding.

    if created_at_override and updated_at_override:
        # This path is for when you explicitly set both for seeding
        final_query = """
        INSERT INTO analysis_results (review_id, result_json, created_at, updated_at)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (review_id) DO UPDATE SET
            result_json = EXCLUDED.result_json,
            updated_at = EXCLUDED.updated_at -- Use the provided updated_at on conflict too
        RETURNING id, review_id, result_json, created_at, updated_at;
        """
        final_params = (
            str(result.review_id),
            json.dumps(result.result_json),
            created_at_override,
            updated_at_override,
        )
    else:
        # Default behavior: let DB handle timestamps
        final_query = """
        INSERT INTO analysis_results (review_id, result_json)
        VALUES (%s, %s)
        ON CONFLICT (review_id) DO UPDATE SET
            result_json = EXCLUDED.result_json,
            updated_at = timezone('utc'::text, now())
        RETURNING id, review_id, result_json, created_at, updated_at;
        """
        final_params = (str(result.review_id), json.dumps(result.result_json))

    try:
        logger.debug(
            f"Executing create_analysis_result_db for review {result.review_id}. Query: '{final_query.strip()}'"
        )
        data = execute_and_fetch_one(final_query, final_params)
        if data:
            # result_json from DB will be a dict if JSONB and RealDictCursor
            # If it's a string, json.loads is needed by Pydantic model
            if isinstance(data.get("result_json"), str):
                try:
                    data["result_json"] = json.loads(data["result_json"])
                except json.JSONDecodeError:
                    logger.error(
                        f"Failed to parse result_json from DB for review {result.review_id} during model validation."
                    )
                    # Keep it as string, Pydantic might complain or handle based on type
            return AnalysisResultItem.model_validate(data)
        logger.warning(
            f"create_analysis_result_db for review {result.review_id} did not return data after upsert."
        )
        return None
    except Exception as e:
        logger.error(
            f"DB Error in create_analysis_result_db for review {result.review_id}: {e}",
            exc_info=True,
        )
        return None


def get_analysis_result_by_review_id_db(
    review_id: uuid.UUID,
) -> Optional[AnalysisResultItem]:
    query = """
    SELECT id, review_id, result_json, created_at, updated_at 
    FROM analysis_results 
    WHERE review_id = %s
    """
    try:
        data = fetch_one(query, (str(review_id),))
        if data:
            if isinstance(data.get("result_json"), str):
                data["result_json"] = json.loads(data["result_json"])
            return AnalysisResultItem.model_validate(data)
        return None
    except Exception as e:
        logger.error(
            f"DB Error in get_analysis_result_by_review_id_db for review {review_id}: {e}",
            exc_info=True,
        )
        return None
