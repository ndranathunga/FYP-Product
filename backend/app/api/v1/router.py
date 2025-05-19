from fastapi import APIRouter
from backend.app.api.v1.endpoints import products_reviews, analysis_stats, prompts
from backend.app.auth.auth_routes import auth_router

api_v1_router = APIRouter()

api_v1_router.include_router(auth_router, tags=["Authentication"])
api_v1_router.include_router(
    products_reviews.router, prefix="/products", tags=["Products & Reviews"]
)
api_v1_router.include_router(analysis_stats.router, tags=["Analysis & Statistics"])
api_v1_router.include_router(prompts.router, tags=["Prompts"])
