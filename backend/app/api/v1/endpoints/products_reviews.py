from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
    Path as FastApiPath,
    BackgroundTasks,
)
from typing import List
import uuid

from backend.app.auth.deps import get_current_user
from backend.app.services.analysis_service import get_analysis_service, AnalysisService
from backend.app.db import schemas as db_schemas
from backend.app.db import products as db_products
from backend.app.db import reviews as db_reviews
from backend.app.db import analysis_results as db_analysis_results
from loguru import logger

router = APIRouter()


# --- Product Endpoints ---
@router.post(
    "/",
    response_model=db_schemas.Product,
    status_code=201,
    summary="Create a new product",
)
async def create_product(
    product_in: db_schemas.ProductCreate, current_user: dict = Depends(get_current_user)
):
    user_id_from_token = uuid.UUID(current_user["user_id"])
    logger.info(f"User {user_id_from_token} creating product: {product_in.name}")
    db_product = db_products.create_product_db(
        product=product_in, user_id=user_id_from_token
    )
    if not db_product:
        raise HTTPException(status_code=500, detail="Could not create product.")

    return db_product


@router.get(
    "/",
    response_model=List[db_schemas.Product],
    summary="Get all products for the current user",
)
async def read_user_products(
    skip: int = 0, limit: int = 100, current_user: dict = Depends(get_current_user)
):
    user_id_from_token = uuid.UUID(current_user["user_id"])
    logger.debug(f"Fetching products for user {user_id_from_token}")
    products_list = db_products.get_products_by_user_db(
        user_id=user_id_from_token, skip=skip, limit=limit
    )
    
    return products_list


@router.get(
    "/{product_id}",
    response_model=db_schemas.Product,
    summary="Get a specific product by ID",
)
async def read_product(
    product_id: uuid.UUID = FastApiPath(
        ..., description="The ID of the product to get"
    ),
    current_user: dict = Depends(get_current_user),
):
    user_id_from_token = uuid.UUID(current_user["user_id"])
    logger.debug(f"Fetching product {product_id} for user {user_id_from_token}")
    db_product = db_products.get_product_by_id_db(
        product_id=product_id, user_id=user_id_from_token
    )
    if db_product is None:
        raise HTTPException(
            status_code=404, detail="Product not found or access denied."
        )
        
    #? Can get the revies as well if needed
    # reviews_list = db_reviews.get_reviews_by_product_db(product_id=db_product.id)
    # populated_reviews = []
    # for review_item in reviews_list:
    #     review_item.analysis_results = db_analysis_results.get_analysis_result_by_review_id_db(review_item.id)
    #     populated_reviews.append(review_item)
    # db_product.reviews = populated_reviews
    
    return db_product


@router.put(
    "/{product_id}", response_model=db_schemas.Product, summary="Update a product"
)
async def update_product(
    product_update: db_schemas.ProductUpdate,
    product_id: uuid.UUID = FastApiPath(
        ..., description="The ID of the product to update"
    ),
    current_user: dict = Depends(get_current_user),
):
    user_id_from_token = uuid.UUID(current_user["user_id"])
    logger.info(f"User {user_id_from_token} updating product {product_id}")
    updated_product = db_products.update_product_db(
        product_id=product_id, product_update=product_update, user_id=user_id_from_token
    )
    if not updated_product:
        raise HTTPException(
            status_code=404,
            detail="Product not found, access denied, or failed to update.",
        )
        
    return updated_product


@router.delete("/{product_id}", status_code=204, summary="Delete a product")
async def delete_product(
    product_id: uuid.UUID = FastApiPath(
        ..., description="The ID of the product to delete"
    ),
    current_user: dict = Depends(get_current_user),
):
    user_id_from_token = uuid.UUID(current_user["user_id"])
    logger.info(f"User {user_id_from_token} deleting product {product_id}")
    deleted = db_products.delete_product_db(
        product_id=product_id, user_id=user_id_from_token
    )
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Product not found, access denied, or failed to delete.",
        )
    return None 


# --- Review Endpoints ---
@router.post(
    "/{product_id}/reviews",
    response_model=db_schemas.Review,
    status_code=201,
    summary="Create a review for a product",
)
async def create_review_for_product(
    review_in: db_schemas.ReviewCreate,
    product_id: uuid.UUID = FastApiPath(
        ..., description="The ID of the product to add review to"
    ),
    current_user: dict = Depends(get_current_user),
    analysis_svc: AnalysisService = Depends(get_analysis_service),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    user_id_from_token = uuid.UUID(current_user["user_id"])
    product = db_products.get_product_by_id_db(
        product_id=product_id, user_id=user_id_from_token
    )
    if not product:
        raise HTTPException(
            status_code=404, detail="Product not found or access denied."
        )

    logger.info(f"User {user_id_from_token} creating review for product {product_id}")
    db_review_obj = db_reviews.create_review_db(review=review_in, product_id=product_id)
    if not db_review_obj:
        raise HTTPException(status_code=500, detail="Could not create review.")

    logger.info(f"Adding analysis of review {db_review_obj.id} to background tasks.")
    background_tasks.add_task(
        analysis_svc.analyze_and_store_review, db_review_obj, user_id_from_token
    )

    db_review_obj.analysis_results = None
    return db_review_obj


@router.get(
    "/{product_id}/reviews",
    response_model=List[db_schemas.Review],
    summary="Get reviews for a product",
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
            status_code=404, detail="Product not found or access denied."
        )

    logger.debug(
        f"Fetching reviews for product {product_id} (user {user_id_from_token})"
    )
    reviews_list = db_reviews.get_reviews_by_product_db(
        product_id=product_id, skip=skip, limit=limit
    )

    for review_item in reviews_list:
        review_item.analysis_results = (
            db_analysis_results.get_analysis_result_by_review_id_db(review_item.id)
        )
    return reviews_list
