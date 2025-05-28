# backend/app/api/v1/endpoints/products_reviews.py
from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
    Path as FastApiPath,
    BackgroundTasks,
)
from typing import List, Optional
import uuid

from backend.app.auth.deps import get_current_user
from backend.app.services.analysis_service import (
    get_analysis_service_instance,
    AnalysisService,
)
from backend.app.db import schemas as db_schemas
from backend.app.db import products as db_products
from backend.app.db import reviews as db_reviews
from backend.app.db import analysis_results as db_analysis_results
from loguru import logger

router = APIRouter()


# --- Product Endpoints ---
@router.post(
    "/", response_model=db_schemas.Product, status_code=201, summary="Create product"
)
async def create_product(
    product_in: db_schemas.ProductCreate, current_user: dict = Depends(get_current_user)
):
    user_id = uuid.UUID(current_user["user_id"])
    db_product = db_products.create_product_db(product=product_in, user_id=user_id)
    if not db_product:
        raise HTTPException(500, "Could not create product.")
    return db_product


@router.get("/", response_model=List[db_schemas.Product], summary="Get user products")
async def read_user_products(
    skip: int = 0, limit: int = 100, current_user: dict = Depends(get_current_user)
):
    user_id = uuid.UUID(current_user["user_id"])
    return db_products.get_products_by_user_db(user_id=user_id, skip=skip, limit=limit)


@router.get(
    "/{product_id}", response_model=db_schemas.Product, summary="Get product by ID"
)
async def read_product(
    product_id: uuid.UUID, current_user: dict = Depends(get_current_user)
):
    user_id = uuid.UUID(current_user["user_id"])
    db_product = db_products.get_product_by_id_db(
        product_id=product_id, user_id=user_id
    )
    if not db_product:
        raise HTTPException(404, "Product not found or access denied.")

    return db_product


@router.put(
    "/{product_id}", response_model=db_schemas.Product, summary="Update product"
)
async def update_product(
    product_update: db_schemas.ProductUpdate,
    product_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(current_user["user_id"])
    updated_product = db_products.update_product_db(
        product_id=product_id, product_update=product_update, user_id=user_id
    )
    if not updated_product:
        raise HTTPException(404, "Product not found or update failed.")
    return updated_product


@router.delete("/{product_id}", status_code=204, summary="Delete product")
async def delete_product(
    product_id: uuid.UUID, current_user: dict = Depends(get_current_user)
):
    user_id = uuid.UUID(current_user["user_id"])
    if not db_products.delete_product_db(product_id=product_id, user_id=user_id):
        raise HTTPException(404, "Product not found or delete failed.")
    return None


# --- Review Endpoints ---
@router.post(
    "/{product_id}/reviews",
    response_model=db_schemas.Review,
    status_code=201,
    summary="Create a review for a product and trigger background analysis",
)
async def create_review_for_product(
    review_in: db_schemas.ReviewCreate,
    product_id: uuid.UUID = FastApiPath(
        ..., description="The ID of the product to add review to"
    ),
    current_user: dict = Depends(get_current_user),
    analysis_svc: AnalysisService = Depends(get_analysis_service_instance),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    user_id_from_token = uuid.UUID(current_user["user_id"])
    product = db_products.get_product_by_id_db(
        product_id=product_id, user_id=user_id_from_token
    )
    if not product:
        raise HTTPException(
            status_code=404, detail="Product not found or access denied for this user."
        )

    logger.info(f"User {user_id_from_token} creating review for product {product_id}")
    db_review_schema_obj: Optional[db_schemas.Review] = db_reviews.create_review_db(
        review=review_in, product_id=product_id
    )
    if not db_review_schema_obj:
        raise HTTPException(status_code=500, detail="Could not create review.")

    logger.info(
        f"Adding analysis of new review {db_review_schema_obj.id} to background tasks for user {user_id_from_token}."
    )
    background_tasks.add_task(
        analysis_svc.analyze_and_store_single_review,
        review_schema_item=db_review_schema_obj,
        user_id_for_context=user_id_from_token,
    )

    return db_review_schema_obj


@router.get(
    "/{product_id}/reviews",
    response_model=List[db_schemas.Review],
    summary="Get reviews for a product (optionally with analysis results)",
)
async def read_reviews_for_product(
    product_id: uuid.UUID = FastApiPath(
        ..., description="The ID of the product to get reviews for"
    ),
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
):
    user_id_from_token = uuid.UUID(current_user["user_id"])
    product = db_products.get_product_by_id_db(
        product_id=product_id, user_id=user_id_from_token
    )
    if not product:
        raise HTTPException(
            status_code=404, detail="Product not found or access denied for this user."
        )

    logger.debug(
        f"Fetching reviews for product {product_id} (user {user_id_from_token})"
    )
    reviews_schema_list: List[db_schemas.Review] = db_reviews.get_reviews_by_product_db(
        product_id=product_id, skip=skip, limit=limit
    )

    for review_item_schema in reviews_schema_list:
        analysis_item: Optional[db_schemas.AnalysisResultItem] = (
            db_analysis_results.get_analysis_result_by_review_id_db(
                review_item_schema.id
            )
        )
        review_item_schema.analysis_results = analysis_item

    return reviews_schema_list
