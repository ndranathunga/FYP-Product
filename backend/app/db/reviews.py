# backend/app/db/reviews.py
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime  # Import datetime
from loguru import logger

# Import the correct function that handles commits for INSERT with RETURNING
from .connection import fetch_one, fetch_all, execute_and_fetch_one
from .schemas import ReviewCreate, ReviewUpdate, Review as ReviewSchema


def create_review_db(
    review: ReviewCreate,
    product_id: uuid.UUID,
    created_at: Optional[datetime] = None,  # Add optional created_at parameter
) -> Optional[ReviewSchema]:
    """
    Creates a review in the database.
    Allows specifying a created_at timestamp, otherwise uses DB default.
    Returns the created review object or None if creation failed.
    """
    # Adjust query and params based on whether created_at is provided
    if created_at:
        query = """
        INSERT INTO reviews (product_id, review_text, customer_id, created_at)
        VALUES (%s, %s, %s, %s) 
        RETURNING id, product_id, review_text, customer_id, created_at;
        """
        # Ensure created_at is timezone-aware if your DB column is TIMESTAMPTZ
        params = (str(product_id), review.review_text, review.customer_id, created_at)
    else:
        # Let DB handle created_at default (e.g., NOW())
        query = """
        INSERT INTO reviews (product_id, review_text, customer_id)
        VALUES (%s, %s, %s)
        RETURNING id, product_id, review_text, customer_id, created_at;
        """
        params = (str(product_id), review.review_text, review.customer_id)

    try:
        logger.debug(
            f"Executing create_review_db. Query: '{query.strip()}', Params: {params}"
        )
        # Use the function that handles commit for INSERT/UPDATE with RETURNING
        data = execute_and_fetch_one(query, params)

        if data:
            logger.success(
                f"Review for product {product_id} created successfully in DB with ID: {data.get('id')}"
            )
            return ReviewSchema.model_validate(data)
        else:
            logger.error(
                f"Review creation failed for product {product_id}. execute_and_fetch_one returned None."
            )
            return None
    except Exception as e:
        logger.error(
            f"Exception in create_review_db for product {product_id}: {e}",
            exc_info=True,
        )
        return None


def get_review_by_id_db(review_id: uuid.UUID) -> Optional[ReviewSchema]:
    query = "SELECT id, product_id, review_text, customer_id, created_at FROM reviews WHERE id = %s"
    data = fetch_one(query, (str(review_id),))
    return ReviewSchema.model_validate(data) if data else None


def get_reviews_by_product_db(
    product_id: uuid.UUID, skip: int = 0, limit: int = 100
) -> List[ReviewSchema]:
    query = "SELECT id, product_id, review_text, customer_id, created_at FROM reviews WHERE product_id = %s ORDER BY created_at DESC LIMIT %s OFFSET %s"
    data_list = fetch_all(query, (str(product_id), limit, skip))
    return [ReviewSchema.model_validate(data) for data in data_list]


def get_all_reviews_with_product_info_for_user_db(
    user_id: uuid.UUID, limit: int = 10000, offset: int = 0
) -> List[Dict[str, Any]]:
    # ... (this function seems okay as it's a SELECT, using fetch_all) ...
    # ... (ensure column names match your actual schema if you modify it) ...
    query = """
    SELECT 
        r.id as review_id, 
        r.review_text, 
        r.customer_id, 
        r.created_at as review_created_at, 
        r.product_id,
        p.name as product_name
    FROM reviews r
    JOIN products p ON r.product_id = p.id
    WHERE p.user_id = %s
    ORDER BY r.created_at DESC
    LIMIT %s OFFSET %s; 
    """
    try:
        data_list = fetch_all(query, (str(user_id), limit, offset))
        return data_list if data_list else []
    except Exception as e:
        logger.error(
            f"Error in get_all_reviews_with_product_info_for_user_db for user {user_id}: {e}",
            exc_info=True,
        )
        return []


def get_all_reviews_with_product_info_db(  # This one is not user-specific
    limit: int = 10000, offset: int = 0
) -> List[Dict[str, Any]]:
    # ... (this function seems okay as it's a SELECT, using fetch_all) ...
    query = """
    SELECT 
        r.id as review_id, r.review_text, r.customer_id, r.created_at as review_created_at, 
        r.product_id, p.name as product_name
    FROM reviews r LEFT JOIN products p ON r.product_id = p.id
    ORDER BY r.created_at DESC LIMIT %s OFFSET %s; 
    """
    data_list = fetch_all(query, (limit, offset))
    return data_list if data_list else []


def update_review_db(
    review_id: uuid.UUID,
    review_update: ReviewUpdate,
    product_id: uuid.UUID,  # product_id for scoping the update
) -> Optional[ReviewSchema]:
    current_review_dict = fetch_one(
        "SELECT * FROM reviews WHERE id = %s AND product_id = %s",  # Ensure product_id match for safety
        (str(review_id), str(product_id)),
    )
    if not current_review_dict:
        logger.warning(
            f"Review {review_id} for product {product_id} not found for update."
        )
        return None

    update_data = review_update.model_dump(exclude_unset=True)
    if not update_data:
        logger.info(
            f"No fields to update for review {review_id}. Returning current review."
        )
        return ReviewSchema.model_validate(current_review_dict)

    set_clause_parts = []
    values = []
    for key, value in update_data.items():
        set_clause_parts.append(f"{key} = %s")
        values.append(value)

    # Add updated_at to the SET clause (assuming reviews table has an updated_at column)
    # If reviews table does not have updated_at, remove this line.
    # For now, let's assume it does NOT, as per your schema image.
    # If it does, uncomment:
    # set_clause_parts.append("updated_at = timezone('utc'::text, now())")

    set_clause_str = ", ".join(set_clause_parts)
    values.extend([str(review_id), str(product_id)])

    # Adjust RETURNING clause if reviews table has updated_at
    query = f"""
    UPDATE reviews SET {set_clause_str} WHERE id = %s AND product_id = %s
    RETURNING id, product_id, review_text, customer_id, created_at 
    """  # Add updated_at to RETURNING if it exists

    try:
        logger.debug(
            f"Executing update_review_db for review {review_id}. Query: '{query.strip()}', Values: {tuple(values)}"
        )
        data = execute_and_fetch_one(query, tuple(values))
        if data:
            logger.success(f"Review {review_id} updated successfully.")
            return ReviewSchema.model_validate(data)
        else:
            logger.error(f"Review {review_id} update failed or did not return data.")
            return None
    except Exception as e:
        logger.error(
            f"Exception in update_review_db for review {review_id}: {e}", exc_info=True
        )
        return None


def delete_review_db(review_id: uuid.UUID, product_id: uuid.UUID) -> bool:
    query = "DELETE FROM reviews WHERE id = %s AND product_id = %s RETURNING id"
    try:
        logger.debug(
            f"Attempting to delete review {review_id} for product {product_id}"
        )
        deleted_record = execute_and_fetch_one(query, (str(review_id), str(product_id)))
        if deleted_record:
            logger.success(f"Review {review_id} deleted successfully.")
            return True
        else:
            logger.warning(
                f"Review {review_id} not found or delete failed (no record returned)."
            )
            return False
    except Exception as e:
        logger.error(
            f"Exception in delete_review_db for review {review_id}: {e}", exc_info=True
        )
        return False
