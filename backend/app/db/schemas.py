import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field


# --- User Schemas ---
class UserBase(BaseModel):
    email: EmailStr
    org_name: str


class UserCreateInput(UserBase):  # For signup request, matching auth_routes
    password: str


class UserInDB(UserBase):
    id: uuid.UUID
    password_hash: str  # Keep for internal use, don't expose in User schema
    created_at: datetime

    class Config:
        from_attributes = True


class User(UserBase):  # Public User Schema
    id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True


# --- Product Schemas ---
class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None


class ProductCreate(ProductBase):
    pass


class ProductUpdate(ProductBase):
    name: Optional[str] = None
    description: Optional[str] = None


class Product(ProductBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    reviews: List["Review"] = []

    class Config:
        from_attributes = True


# --- Review Schemas ---
class ReviewBase(BaseModel):
    review_text: str
    customer_id: Optional[str] = None


class ReviewCreate(ReviewBase):
    pass


class ReviewUpdate(BaseModel):
    review_text: Optional[str] = None
    customer_id: Optional[str] = None


class Review(ReviewBase):
    id: uuid.UUID
    product_id: uuid.UUID
    created_at: datetime
    analysis_results: Optional["AnalysisResultItem"] = None

    class Config:
        from_attributes = True


# --- Analysis Result Schemas ---
class AnalysisResultBase(BaseModel):
    language: Optional[str] = None
    sentiment: Optional[int] = None
    confidence: Optional[float] = None
    result_json: Optional[Dict[str, Any]] = None


class AnalysisResultCreate(AnalysisResultBase):
    review_id: uuid.UUID


class AnalysisResultItem(
    AnalysisResultBase
):  # To avoid conflict with main.py's AnalysisResult
    id: uuid.UUID
    review_id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True


# Update forward references for Pydantic v2
Product.model_rebuild()
Review.model_rebuild()
