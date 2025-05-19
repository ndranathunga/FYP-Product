import uuid
import json
from typing import List, Optional, Dict, Any

from .connection import fetch_one, fetch_all
from .schemas import AnalysisResultCreate, AnalysisResultItem


def create_analysis_result_db(
    result: AnalysisResultCreate,
) -> Optional[AnalysisResultItem]:
    query = """
    INSERT INTO analysis_results (review_id, language, sentiment, confidence, result_json)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (review_id) DO UPDATE SET
        language = EXCLUDED.language,
        sentiment = EXCLUDED.sentiment,
        confidence = EXCLUDED.confidence,
        result_json = EXCLUDED.result_json,
        created_at = timezone('utc'::text, now())
    RETURNING id, review_id, language, sentiment, confidence, result_json, created_at
    """
    result_json_pg = (
        json.dumps(result.result_json)
        if isinstance(result.result_json, dict)
        else result.result_json
    )
    data = fetch_one(
        query,
        (
            result.review_id,
            result.language,
            result.sentiment,
            result.confidence,
            result_json_pg,
        ),
    )
    return AnalysisResultItem.model_validate(data) if data else None


def get_analysis_result_by_review_id_db(
    review_id: uuid.UUID,
) -> Optional[AnalysisResultItem]:
    query = "SELECT * FROM analysis_results WHERE review_id = %s"
    data = fetch_one(query, (review_id,))
    return AnalysisResultItem.model_validate(data) if data else None


# --- Functions for Stats Aggregation ---
def get_user_stats_summary_db(user_id: uuid.UUID) -> List[Dict[str, Any]]:
    """Aggregates stats for language, sentiment distribution for a user"""
    query = """
    SELECT
        ar.language,
        ar.sentiment,
        COUNT(*) as count
    FROM analysis_results ar
    JOIN reviews r ON ar.review_id = r.id
    JOIN products p ON r.product_id = p.id
    WHERE p.user_id = %s AND ar.language IS NOT NULL AND ar.sentiment IS NOT NULL
    GROUP BY ar.language, ar.sentiment;
    """
    return fetch_all(query, (user_id,))


def get_total_reviews_processed_for_user_db(user_id: uuid.UUID) -> int:
    query = """
    SELECT COUNT(DISTINCT ar.review_id)
    FROM analysis_results ar
    JOIN reviews r ON ar.review_id = r.id
    JOIN products p ON r.product_id = p.id
    WHERE p.user_id = %s;
    """
    result = fetch_one(query, (user_id,))
    return result["count"] if result else 0


def get_total_reviews_in_dataset_for_user_db(user_id: uuid.UUID) -> int:
    query = """
    SELECT COUNT(r.id)
    FROM reviews r
    JOIN products p ON r.product_id = p.id
    WHERE p.user_id = %s;
    """
    result = fetch_one(query, (user_id,))
    return result["count"] if result else 0
