from pydantic import BaseModel
from typing import Dict, Any, Optional

class AdhocReviewInput(BaseModel):
    text: str

class AdhocAnalysisResult(BaseModel):
    language: Optional[Dict[str, Any]] = None
    sentiment: Optional[Dict[str, Any]] = None

class StatsResponse(BaseModel):
    stats: Optional[Dict[str, Any]] = None