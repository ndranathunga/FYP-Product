# backend/app/api/v1/schemas.py
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List


class AdhocReviewInput(BaseModel):
    text: str
    product_id_context: Optional[str] = Field(
        "ad_hoc_product", description="Optional product context for ad-hoc analysis"
    )


class AdhocAspectAnalysisResult(BaseModel):
    review_id: str
    product_id: str
    product_name: Optional[str] = None
    aspects_data: List[Dict[str, Any]] = Field(default_factory=list)
    raw_model_output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ProductAspectRatingDetail(BaseModel):
    average_rating: float
    review_count: int
    rating_distribution: Dict[str, int]


class ProductUIDashboardSummary(BaseModel):
    Current_Ratings: Optional[Dict[str, float]] = Field(None, alias="Current Ratings")
    Summary_Ratings: Optional[Dict[str, float]] = Field(None, alias="Summary Ratings")
    Summary: Optional[str] = None
    Recommendations: Optional[str] = None
    Anomaly: Optional[bool] = None

    class Config:
        allow_population_by_field_name = True
        from_attributes = True


class ProductOverallStats(BaseModel):
    product_id: str
    product_name: str
    total_reviews_analyzed: int
    aspects_summary: Dict[str, ProductAspectRatingDetail]
    dashboard_summary: Optional[ProductUIDashboardSummary] = None


class UserProductsStatsResponse(BaseModel):
    products_data: Dict[str, ProductOverallStats] = Field(default_factory=dict)
    total_reviews_processed_this_user: Optional[int] = None
    total_reviews_in_dataset_this_user: Optional[int] = None
    status: Optional[str] = None
    message: Optional[str] = None
