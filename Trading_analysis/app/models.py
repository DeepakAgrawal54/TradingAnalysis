# app/models.py
from pydantic import BaseModel, Field
from typing import Optional, Dict
from enum import Enum

class AnalysisType(str, Enum):
    SHORT = "short"
    LONG = "long"

class TradingRequest(BaseModel):
    symbol: str = Field(..., description="Stock ticker symbol")
    analysis_type: AnalysisType = Field(
        default=AnalysisType.SHORT,
        description="Type of analysis to perform"
    )

class AnalysisResponse(BaseModel):
    symbol: str
    news_analysis: str
    technical_analysis: str
    recommendation: str
    ownership_analysis: Optional[str]
    economic_analysis: Optional[str]
    peer_analysis: Optional[str]