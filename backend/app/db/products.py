# backend/app/db/products.py
import uuid
from typing import List, Optional
from datetime import datetime  # Import datetime
from loguru import logger

# Import the correct function that handles commits for INSERT with RETURNING
from .connection import fetch_one, fetch_all, execute_and_fetch_one
from .schemas import (
    ProductCreate,
    ProductUpdate,
    Product as ProductSchema,
)


def create_product_db(
    product: ProductCreate,
    user_id: uuid.UUID,
    created_at: Optional[datetime] = None,  # Add optional created_at parameter
) -> Optional[ProductSchema]:
    """
    Creates a product in the database.
    Allows specifying a created_at timestamp, otherwise uses DB default.
    Returns the created product object or None if creation failed.
    """
    # Adjust query and params based on whether created_at is provided
    if created_at:
        query = """
        INSERT INTO products (user_id, name, description, created_at, updated_at) 
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, user_id, name, description, created_at, updated_at;
        """
        # Ensure created_at and updated_at are passed as timezone-aware if your DB column is TIMESTAMPTZ
        params = (
            str(user_id),
            product.name,
            product.description,
            created_at,
            created_at,
        )  # Set updated_at to created_at initially
    else:
        # Let DB handle created_at and updated_at defaults (e.g., NOW())
        query = """
        INSERT INTO products (user_id, name, description) 
        VALUES (%s, %s, %s)
        RETURNING id, user_id, name, description, created_at, updated_at;
        """
        params = (str(user_id), product.name, product.description)

    try:
        logger.debug(
            f"Executing create_product_db. Query: '{query.strip()}', Params: {params}"
        )
        # Use the function that handles commit for INSERT/UPDATE with RETURNING
        created_product_dict = execute_and_fetch_one(query, params)

        if created_product_dict:
            logger.success(
                f"Product '{product.name}' (User: {user_id}) created successfully in DB with ID: {created_product_dict.get('id')}"
            )
            return ProductSchema.model_validate(created_product_dict)
        else:
            logger.error(
                f"Product creation failed for user {user_id}, name '{product.name}'. execute_and_fetch_one returned None."
            )
            return None

    except Exception as e:
        logger.error(
            f"Exception in create_product_db for user {user_id}, name '{product.name}': {e}",
            exc_info=True,
        )
        return None


def get_product_by_id_db(
    product_id: uuid.UUID, user_id: uuid.UUID
) -> Optional[ProductSchema]:
    query = "SELECT id, user_id, name, description, created_at, updated_at FROM products WHERE id = %s AND user_id = %s"
    data = fetch_one(query, (str(product_id), str(user_id)))
    return ProductSchema.model_validate(data) if data else None


def get_products_by_user_db(
    user_id: uuid.UUID, skip: int = 0, limit: int = 100
) -> List[ProductSchema]:
    query = """
    SELECT 
        p.id, 
        p.user_id, 
        p.name, 
        p.description, 
        p.created_at, 
        p.updated_at,
        (SELECT COUNT(*) FROM reviews r WHERE r.product_id = p.id) as review_count
    FROM products p
    WHERE p.user_id = %s 
    ORDER BY p.created_at DESC 
    LIMIT %s OFFSET %s;
    """
    # Ensure your connection.py's fetch_all can handle the 'review_count' alias
    data_list = fetch_all(query, (str(user_id), limit, skip))

    products_with_count = []
    if data_list:
        for data_item in data_list:
            # The 'review_count' from the DB will be an integer.
            # Pydantic will validate it against ProductSchema.
            products_with_count.append(ProductSchema.model_validate(data_item))
    return products_with_count


def update_product_db(
    product_id: uuid.UUID, product_update: ProductUpdate, user_id: uuid.UUID
) -> Optional[ProductSchema]:
    current_product_dict = fetch_one(
        "SELECT * FROM products WHERE id = %s AND user_id = %s",
        (str(product_id), str(user_id)),
    )
    if not current_product_dict:
        return None

    update_data = product_update.model_dump(exclude_unset=True)
    if not update_data:
        logger.info(
            f"No fields to update for product {product_id}. Returning current product."
        )
        return ProductSchema.model_validate(current_product_dict)

    set_clause_parts = []
    values = []
    for key, value in update_data.items():
        set_clause_parts.append(f"{key} = %s")
        values.append(value)

    set_clause_parts.append(
        "updated_at = timezone('utc'::text, now())"
    )  # Always update updated_at
    set_clause_str = ", ".join(set_clause_parts)

    values.extend([str(product_id), str(user_id)])

    query = f"""
    UPDATE products SET {set_clause_str}
    WHERE id = %s AND user_id = %s
    RETURNING id, user_id, name, description, created_at, updated_at; 
    """
    try:
        logger.debug(
            f"Executing update_product_db for product {product_id}. Query: '{query.strip()}', Values: {tuple(values)}"
        )
        data = execute_and_fetch_one(query, tuple(values))

        if data:
            logger.success(f"Product {product_id} updated successfully in DB.")
            return ProductSchema.model_validate(data)
        else:
            logger.error(f"Product {product_id} update failed or did not return data.")
            return None
    except Exception as e:
        logger.error(
            f"Exception in update_product_db for product {product_id}: {e}",
            exc_info=True,
        )
        return None


def delete_product_db(product_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    query = "DELETE FROM products WHERE id = %s AND user_id = %s RETURNING id"
    try:
        logger.debug(f"Attempting to delete product {product_id} for user {user_id}")
        deleted_record = execute_and_fetch_one(query, (str(product_id), str(user_id)))
        if deleted_record:
            logger.success(
                f"Product {product_id} deleted successfully for user {user_id}."
            )
            return True
        else:
            logger.warning(
                f"Product {product_id} not found or delete failed for user {user_id} (no record returned)."
            )
            return False
    except Exception as e:
        logger.error(
            f"Exception in delete_product_db for product {product_id}: {e}",
            exc_info=True,
        )
        return False
