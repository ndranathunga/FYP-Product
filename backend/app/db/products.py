import uuid
from typing import List, Optional


from .connection import fetch_one, fetch_all, execute_query
from .schemas import (
    ProductCreate,
    ProductUpdate,
    Product as ProductSchema,
)


def create_product_db(
    product: ProductCreate, user_id: uuid.UUID
) -> Optional[ProductSchema]:
    query = """
    INSERT INTO products (user_id, name, description)
    VALUES (%s, %s, %s)
    RETURNING id, user_id, name, description, created_at
    """
    data = fetch_one(query, (str(user_id), product.name, product.description))
    return ProductSchema.model_validate(data) if data else None


def get_product_by_id_db(
    product_id: uuid.UUID, user_id: uuid.UUID
) -> Optional[ProductSchema]:
    query = "SELECT * FROM products WHERE id = %s AND user_id = %s"
    data = fetch_one(query, (str(product_id), str(user_id)))
    return ProductSchema.model_validate(data) if data else None


def get_products_by_user_db(
    user_id: uuid.UUID, skip: int = 0, limit: int = 100
) -> List[ProductSchema]:
    query = "SELECT * FROM products WHERE user_id = %s ORDER BY created_at DESC LIMIT %s OFFSET %s"
    data_list = fetch_all(query, (str(user_id), limit, skip))
    return [ProductSchema.model_validate(data) for data in data_list]


def update_product_db(
    product_id: uuid.UUID, product_update: ProductUpdate, user_id: uuid.UUID
) -> Optional[ProductSchema]:
    # Fetch current product to handle partial updates
    current_product = get_product_by_id_db(product_id, user_id)
    if not current_product:
        return None

    update_data = product_update.model_dump(exclude_unset=True)
    if not update_data:  # No fields to update
        return current_product

    set_clause = ", ".join([f"{key} = %s" for key in update_data.keys()])
    values = list(update_data.values()) + [str(product_id), str(user_id)]

    query = f"""
    UPDATE products SET {set_clause}
    WHERE id = %s AND user_id = %s
    RETURNING id, user_id, name, description, created_at
    """
    data = fetch_one(query, tuple(values))
    return ProductSchema.model_validate(data) if data else None


def delete_product_db(product_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    query = "DELETE FROM products WHERE id = %s AND user_id = %s RETURNING id"
    deleted = fetch_one(query, (str(product_id), str(user_id)))
    return deleted is not None
