import uuid
from typing import List, Optional

from .connection import fetch_one, fetch_all
from .schemas import ReviewCreate, ReviewUpdate, Review as ReviewSchema


def create_review_db(
    review: ReviewCreate, product_id: uuid.UUID
) -> Optional[ReviewSchema]:
    # Ownership of product_id should be checked by the caller (service/API layer)
    query = """
    INSERT INTO reviews (product_id, review_text, customer_id)
    VALUES (%s, %s, %s)
    RETURNING id, product_id, review_text, customer_id, created_at
    """
    data = fetch_one(query, (str(product_id), review.review_text, review.customer_id))
    return ReviewSchema.model_validate(data) if data else None


def get_review_by_id_db(review_id: uuid.UUID) -> Optional[ReviewSchema]:
    # For user-specific access, join with products table and filter by user_id in service/API layer
    query = "SELECT * FROM reviews WHERE id = %s"
    data = fetch_one(query, (str(review_id),))
    return ReviewSchema.model_validate(data) if data else None


def get_reviews_by_product_db(
    product_id: uuid.UUID, skip: int = 0, limit: int = 100
) -> List[ReviewSchema]:
    # Ownership of product_id should be checked by the caller
    query = "SELECT * FROM reviews WHERE product_id = %s ORDER BY created_at DESC LIMIT %s OFFSET %s"
    data_list = fetch_all(query, (str(product_id), limit, skip))
    return [ReviewSchema.model_validate(data) for data in data_list]


def get_all_reviews_for_user_db(user_id: uuid.UUID) -> List[ReviewSchema]:
    query = """
    SELECT r.id, r.product_id, r.review_text, r.customer_id, r.created_at
    FROM reviews r
    JOIN products p ON r.product_id = p.id
    WHERE p.user_id = %s
    ORDER BY r.created_at DESC
    """
    data_list = fetch_all(query, (str(user_id),))
    return [ReviewSchema.model_validate(data) for data in data_list]


def update_review_db(
    review_id: uuid.UUID, review_update: ReviewUpdate, product_id: uuid.UUID
) -> Optional[ReviewSchema]:
    # product_id is used to ensure the review belongs to a product owned by the user (checked by caller)
    current_review_dict = fetch_one(
        "SELECT * from reviews where id = %s and product_id = %s",
        (str(review_id), product_id),
    )
    if not current_review_dict:
        return None

    update_data = review_update.model_dump(exclude_unset=True)
    if not update_data:
        return ReviewSchema.model_validate(current_review_dict)

    set_clause = ", ".join([f"{key} = %s" for key in update_data.keys()])
    values = list(update_data.values()) + [str(review_id), str(product_id)]

    query = f"""
    UPDATE reviews SET {set_clause}
    WHERE id = %s AND product_id = %s
    RETURNING id, product_id, review_text, customer_id, created_at
    """
    data = fetch_one(query, tuple(values))
    return ReviewSchema.model_validate(data) if data else None


def delete_review_db(review_id: uuid.UUID, product_id: uuid.UUID) -> bool:
    query = "DELETE FROM reviews WHERE id = %s AND product_id = %s RETURNING id"
    deleted = fetch_one(query, (str(review_id), str(product_id)))
    return deleted is not None
