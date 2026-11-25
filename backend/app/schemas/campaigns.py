"""Campaign schemas."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FieldStrategyConfig(BaseModel):
    strategy: str = Field(default="constant", pattern="^(constant|random|custom)$")
    value: Optional[str] = None


class CampaignCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    senderName: Optional[str] = None
    senderEmail: Optional[str] = None
    subjectLine: Optional[str] = None
    messageBody: Optional[str] = None
    maxWebsites: int = Field(default=500, ge=1, le=100000)
    websiteIds: List[Any] = Field(default_factory=list)
    fieldStrategies: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    approved: bool = False


class CampaignUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    senderName: Optional[str] = None
    senderEmail: Optional[str] = None
    subjectLine: Optional[str] = None
    messageBody: Optional[str] = None
    maxWebsites: Optional[int] = Field(default=None, ge=1, le=100000)
    websiteIds: Optional[List[Any]] = None
    fieldStrategies: Optional[Dict[str, Dict[str, Any]]] = None


class FillFormsRequest(BaseModel):
    userdata: Dict[str, Any] = Field(default_factory=dict)
    maxwebsites: int = Field(default=50, ge=1, le=5000)
    maxWebsites: Optional[int] = None
    userData: Optional[Dict[str, Any]] = None
